# initializerLambda/index.py
import os
import json
import boto3 # type: ignore
import psycopg2 # type: ignore
import time
from botocore.exceptions import ClientError # type: ignore
from data import customers, orders

def get_secret(secret_arn):
    """
    Retrieve a secret from AWS Secrets Manager.
    """
    # amazonq-ignore-next-line
    # print(f"Getting secret for ARN: {secret_arn}")
    session = boto3.Session()
    secrets_client = session.client("secretsmanager")
    try:
        get_secret_value_response = secrets_client.get_secret_value(
            SecretId=secret_arn
        )
    except ClientError as e:
        print(f"Error getting secret: {str(e)}")
        raise e
    else:
        if "SecretString" in get_secret_value_response:
            secret = get_secret_value_response["SecretString"]
            return json.loads(secret)
        else:
            raise ValueError("Unsupported secret type")

def get_db_connection(secret_arn, max_retries=5, retry_delay=5):
    """
    Get database connection with retries
    """
    db_secrets = get_secret(secret_arn)
    
    for attempt in range(max_retries):
        # amazonq-ignore-next-line
        try:
            conn = psycopg2.connect(
                host=db_secrets['host'],
                port=int(db_secrets.get('port', 5432)),
                database=db_secrets.get('dbname', 'chatbotdb'),
                user=db_secrets['username'],
                password=db_secrets['password'],
                connect_timeout=10
            )
            print(f"Successfully connected to database on attempt {attempt + 1}")
            return conn
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                print(f"Failed to connect after {max_retries} attempts: {str(e)}")
                raise e
            print(f"Connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

def create_tables(conn):
    """
    Create the necessary database tables
    """
    with conn.cursor() as cur:
        # Create customers table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(255) NOT NULL,
                username VARCHAR(255) NOT NULL
            )
        """)

        # Create orders table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(255) PRIMARY KEY,
                customer_id VARCHAR(255) NOT NULL,
                product VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                status VARCHAR(255) NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        """)
        
        conn.commit()
        print("Tables created successfully")

def insert_sample_data(conn):
    """
    Insert sample data into the database from data.py
    """
    try:
        with conn.cursor() as cur:
            # Insert customers
            for customer in customers:
                cur.execute("""
                    INSERT INTO customers (id, name, email, phone, username)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    customer['id'],
                    customer['name'],
                    customer['email'],
                    customer['phone'],
                    customer['username']
                ))

            # Insert orders
            for order in orders:
                cur.execute("""
                    INSERT INTO orders (id, customer_id, product, quantity, price, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    order['id'],
                    order['customer_id'],
                    order['product'],
                    order['quantity'],
                    order['price'],
                    order['status']
                ))

            conn.commit()
            print("Sample data inserted successfully")
    except Exception as e:
        print(f"Error inserting sample data: {str(e)}")
        conn.rollback()
        raise e

def handler(event, context):
    """
    Lambda handler for database initialization
    """
    print(f"Event: {json.dumps(event)}")
    print(f"Environment variables: {dict(os.environ)}")

    try:
        # Get configuration
        secret_arn = os.environ.get('DB_SECRET_ARN')
        max_retries = int(os.environ.get('RETRY_ATTEMPTS', '5'))
        retry_delay = int(os.environ.get('RETRY_DELAY', '5'))

        if not secret_arn:
            raise ValueError("DB_SECRET_ARN environment variable not set")

        # Handle different CloudFormation events
        request_type = event.get('RequestType', '')
        if request_type in ['Create', 'Update']:
            # Connect to database
            conn = get_db_connection(secret_arn, max_retries, retry_delay)
            try:
                # Initialize database
                create_tables(conn)
                insert_sample_data(conn)
                
                return {
                    'PhysicalResourceId': 'DatabaseInitialized',
                    'Data': {
                        'Message': 'Database initialized successfully'
                    }
                }
            finally:
                conn.close()
        elif request_type == 'Delete':
            # Handle deletion if needed
            return {
                'PhysicalResourceId': event.get('PhysicalResourceId'),
                'Data': {
                    'Message': 'Nothing to delete'
                }
            }
        else:
            raise ValueError(f"Unsupported request type: {request_type}")

    except Exception as e:
        print(f"Error: {str(e)}")
        raise e
