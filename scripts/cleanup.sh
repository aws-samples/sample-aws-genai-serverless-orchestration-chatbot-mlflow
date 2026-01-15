#!/bin/bash
set -e

# Get the project root directory (one level up from scripts)
PROJECT_ROOT=$(pwd)

echo "🧹 Cleaning up AWS GenAI Serverless Orchestration Chatbot with MLflow..."

# Constants
BACKEND_STACK="BedrockChatbot-Backend"
FRONTEND_STACK="BedrockChatbot-Frontend"

# Function to check if stack exists
stack_exists() {
    aws cloudformation describe-stacks --stack-name "$1" &>/dev/null
}

# Function to empty S3 buckets from stack outputs
empty_buckets_from_stack() {
    local stack_name="$1"
    
    echo "🪣 Getting S3 buckets from stack: $stack_name"
    
    # Get bucket names from stack outputs
    local buckets=$(aws cloudformation describe-stacks --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?contains(OutputKey, 'Bucket')].OutputValue" --output text 2>/dev/null || echo "")
    
    if [[ -n "$buckets" && "$buckets" != "None" ]]; then
        for bucket in $buckets; do
            if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
                echo "🗑️  Emptying bucket: $bucket"
                aws s3 rm "s3://$bucket" --recursive 2>/dev/null || true
            fi
        done
    else
        echo "ℹ️  No buckets found in stack outputs"
    fi
}

# Function to cleanup security group cross-references
cleanup_security_groups() {
    local stack_name="$1"
    
    echo "🔒 Checking for security group cross-references..."
    
    # Get VPC ID from stack
    local vpc_id=$(aws cloudformation describe-stacks --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='VpcId'].OutputValue" --output text 2>/dev/null || echo "")
    
    if [[ -z "$vpc_id" || "$vpc_id" == "None" ]]; then
        echo "ℹ️  No VPC ID found in stack outputs"
        return 0
    fi
    
    echo "🌐 Found VPC: $vpc_id"
    
    # Find SageMaker NFS security groups (they have predictable names)
    local sg_inbound=$(aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=group-name,Values=security-group-for-inbound-nfs-*" \
        --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "")
    
    local sg_outbound=$(aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=group-name,Values=security-group-for-outbound-nfs-*" \
        --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "")
    
    if [[ -n "$sg_inbound" && "$sg_inbound" != "None" && -n "$sg_outbound" && "$sg_outbound" != "None" ]]; then
        echo "🔒 Found SageMaker NFS security groups: $sg_inbound, $sg_outbound"
        
        # Remove cross-references
        echo "🗑️  Removing security group cross-references..."
        aws ec2 revoke-security-group-ingress --group-id "$sg_inbound" --protocol tcp --port 988 --source-group "$sg_outbound" 2>/dev/null || true
        aws ec2 revoke-security-group-ingress --group-id "$sg_inbound" --protocol tcp --port 1018-1023 --source-group "$sg_outbound" 2>/dev/null || true
        aws ec2 revoke-security-group-ingress --group-id "$sg_inbound" --protocol tcp --port 2049 --source-group "$sg_outbound" 2>/dev/null || true
        
        aws ec2 revoke-security-group-egress --group-id "$sg_outbound" --protocol tcp --port 988 --source-group "$sg_inbound" 2>/dev/null || true
        aws ec2 revoke-security-group-egress --group-id "$sg_outbound" --protocol tcp --port 1018-1023 --source-group "$sg_inbound" 2>/dev/null || true
        aws ec2 revoke-security-group-egress --group-id "$sg_outbound" --protocol tcp --port 2049 --source-group "$sg_inbound" 2>/dev/null || true
        
        # Delete security groups
        echo "🗑️  Deleting security groups..."
        aws ec2 delete-security-group --group-id "$sg_inbound" 2>/dev/null || true
        aws ec2 delete-security-group --group-id "$sg_outbound" 2>/dev/null || true
        
        echo "✅ Security groups cleaned up"
    else
        echo "ℹ️  No SageMaker NFS security groups found"
    fi
}

# Function to delete SageMaker EFS file systems
cleanup_sagemaker_efs() {
    local stack_name="$1"
    
    echo "🗂️  Checking for SageMaker EFS file systems to cleanup..."
    
    # Get SageMaker Domain ID from stack
    local domain_id=$(aws cloudformation describe-stacks --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='SageMakerDomainId'].OutputValue" --output text 2>/dev/null || echo "")
    
    if [[ -z "$domain_id" || "$domain_id" == "None" ]]; then
        echo "ℹ️  No SageMaker Domain ID found in stack outputs"
        return 0
    fi
    
    echo "🔍 Found SageMaker Domain ID: $domain_id"
    
    # Get VPC ID from SageMaker domain
    local vpc_id=$(aws sagemaker describe-domain --domain-id "$domain_id" \
        --query "VpcId" --output text 2>/dev/null || echo "")
    
    if [[ -z "$vpc_id" || "$vpc_id" == "None" ]]; then
        echo "⚠️  Could not get VPC ID from SageMaker domain"
        return 0
    fi
    
    echo "🌐 SageMaker domain is in VPC: $vpc_id"
    
    # Find EFS file systems that might belong to SageMaker
    local all_efs=$(aws efs describe-file-systems --query "FileSystems[].FileSystemId" --output text 2>/dev/null || echo "")
    
    if [[ -z "$all_efs" || "$all_efs" == "None" ]]; then
        echo "ℹ️  No EFS file systems found"
        return 0
    fi
    
    # Check each EFS file system
    for efs_id in $all_efs; do
        echo "🔍 Checking EFS: $efs_id"
        
        # First filter: Check if EFS has mount targets in our VPC
        local mount_targets=$(aws efs describe-mount-targets --file-system-id "$efs_id" \
            --query "MountTargets[?VpcId=='$vpc_id'].MountTargetId" --output text 2>/dev/null || echo "")
        
        if [[ -n "$mount_targets" && "$mount_targets" != "None" ]]; then
            echo "🔗 EFS $efs_id has mount targets in our VPC"
            
            # Second filter: Check if EFS has the SageMaker tag with our domain ID
            local sagemaker_tag=$(aws efs describe-tags --file-system-id "$efs_id" \
                --query "Tags[?Key=='ManagedByAmazonSageMakerResource'].Value" --output text 2>/dev/null || echo "")
            
            if [[ -n "$sagemaker_tag" && "$sagemaker_tag" != "None" ]]; then
                echo "🏷️  Found SageMaker tag: $sagemaker_tag"
                
                # Extract domain ID from the ARN (format: arn:aws:sagemaker:region:account:domain/d-xxxxxxxxx)
                local tag_domain_id=$(echo "$sagemaker_tag" | sed 's/.*domain\///')
                
                if [[ "$tag_domain_id" == "$domain_id" ]]; then
                    echo "✅ Confirmed: EFS $efs_id belongs to our SageMaker domain $domain_id"
                    
                    # Step 1: Delete EFS access points first
                    echo "🔍 Checking for EFS access points..."
                    local access_points=$(aws efs describe-access-points --file-system-id "$efs_id" \
                        --query "AccessPoints[].AccessPointId" --output text 2>/dev/null || echo "")
                    
                    if [[ -n "$access_points" && "$access_points" != "None" ]]; then
                        for ap_id in $access_points; do
                            echo "🗑️  Deleting EFS access point: $ap_id"
                            aws efs delete-access-point --access-point-id "$ap_id" 2>/dev/null || true
                        done
                        echo "⏳ Waiting for access points to be deleted..."
                        sleep 10
                    fi
                    
                    # Step 2: Delete mount targets
                    echo "🗑️  Deleting mount targets..."
                    for mount_target in $mount_targets; do
                        echo "🗑️  Deleting mount target: $mount_target"
                        aws efs delete-mount-target --mount-target-id "$mount_target" 2>/dev/null || true
                    done
                    
                    # Step 3: Wait for mount targets to be completely deleted with proper polling
                    echo "⏳ Waiting for mount targets to be deleted..."
                    local max_wait=300  # 5 minutes max wait
                    local wait_time=0
                    
                    while [[ $wait_time -lt $max_wait ]]; do
                        local remaining_targets=$(aws efs describe-mount-targets --file-system-id "$efs_id" \
                            --query "MountTargets[?VpcId=='$vpc_id'].MountTargetId" --output text 2>/dev/null || echo "")
                        
                        if [[ -z "$remaining_targets" || "$remaining_targets" == "None" ]]; then
                            echo "All mount targets have been deleted"
                            break
                        fi
                        
                        echo "Still waiting for mount targets to be deleted... ($wait_time/$max_wait seconds)"
                        sleep 15
                        wait_time=$((wait_time + 15))
                    done
                    
                    if [[ $wait_time -ge $max_wait ]]; then
                        echo "⚠️ Warning: Timeout waiting for mount targets to be deleted. Proceeding anyway..."
                    fi
                    
                    # Step 4: Delete the EFS file system
                    echo "Deleting EFS file system: $efs_id"
                    local delete_attempts=0
                    local max_attempts=5
                    
                    while [[ $delete_attempts -lt $max_attempts ]]; do
                        if aws efs delete-file-system --file-system-id "$efs_id" 2>/dev/null; then
                            echo "✅ Successfully initiated deletion of EFS: $efs_id"
                            break
                        else
                            delete_attempts=$((delete_attempts + 1))
                            echo "Failed to delete EFS (attempt $delete_attempts/$max_attempts). Retrying in 10 seconds..."
                            sleep 10
                        fi
                    done
                    
                    if [[ $delete_attempts -ge $max_attempts ]]; then
                        echo "❌ Failed to delete EFS $efs_id after $max_attempts attempts"
                        echo "   You may need to manually delete this EFS file system"
                    fi
                else
                    echo "EFS $efs_id belongs to different SageMaker domain: $tag_domain_id (ours: $domain_id) - skipping"
                fi
            else
                echo "EFS $efs_id in our VPC but no SageMaker tag found - skipping"
            fi
        fi
    done
}

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
  echo "❌ AWS CLI is not configured or credentials are invalid."
  echo "   Run: aws configure"
  exit 1
fi

# Ask for confirmation
echo "⚠️  This will destroy ALL resources in your AWS account!"
read -p "Continue with cleanup? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🚫 Cleanup cancelled"
    exit 1
fi

# Get the project root directory 
PROJECT_ROOT=$(pwd)

# Check for Python virtual environment
if [ ! -d ".venv" ]; then
  echo "❌ Python virtual environment not found. Run: ./scripts/install.sh"
  exit 1
fi
# Activate the virtual environment
source .venv/bin/activate
echo "📦 Using Python virtual environment..."

# Load nvm and use Node.js v22.17.1
echo "📦 Loading Node.js v22.17.1..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Use Node.js v22.17.1 if available
if command -v nvm &> /dev/null; then
  nvm use 22.17.1
  echo "✅ Using Node.js $(node -v)"
else
  echo "⚠️  nvm not found. Please run ./scripts/install.sh first"
fi

# Navigate to infra directory
cd "$PROJECT_ROOT/infra"

# Pre-cleanup: Handle S3 and EFS before CDK destroy
echo "🧹 Performing pre-cleanup..."

# Frontend stack: Empty S3 buckets
if stack_exists "$FRONTEND_STACK"; then
    echo "🎨 Frontend stack found - emptying S3 buckets..."
    empty_buckets_from_stack "$FRONTEND_STACK"
fi

# Backend stack: Empty S3 buckets, clean EFS, and security groups
if stack_exists "$BACKEND_STACK"; then
    echo "⚙️  Backend stack found - emptying S3 buckets, cleaning EFS, and security groups..."
    empty_buckets_from_stack "$BACKEND_STACK"
    cleanup_sagemaker_efs "$BACKEND_STACK"
    cleanup_security_groups "$BACKEND_STACK"
fi

echo "✅ Pre-cleanup completed."

# Use CDK destroy with retry mechanism
echo "💥 Destroying all stacks..."
cd "$PROJECT_ROOT/infra"

# Retry CDK destroy up to 3 times
max_attempts=3
attempt=1

while [[ $attempt -le $max_attempts ]]; do
    echo "🔄 CDK destroy attempt $attempt/$max_attempts..."
    
    if cdk destroy --app "python3 app.py" --all --force; then
        echo "✅ CDK destroy completed successfully"
        break
    else
        echo "❌ CDK destroy failed on attempt $attempt"
        
        if [[ $attempt -lt $max_attempts ]]; then
            echo "⏳ Waiting 30 seconds before retry..."
            sleep 30
            
            # Additional cleanup between retries
            echo "🧹 Performing additional cleanup before retry..."
            if stack_exists "$BACKEND_STACK"; then
                cleanup_security_groups "$BACKEND_STACK"
            fi
        else
            echo "❌ CDK destroy failed after $max_attempts attempts"
            echo "   Some resources may need manual cleanup in AWS Console"
            exit 1
        fi
    fi
    
    attempt=$((attempt + 1))
done

# Clean up local files
echo "🧹 Cleaning up local files..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true
rm -rf ./cdk.out 2>/dev/null || true
rm -rf ./infra/cdk.out 2>/dev/null || true

echo "🎉 Cleanup completed successfully!"
