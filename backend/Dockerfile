FROM public.ecr.aws/lambda/python:3.12-x86_64

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements file first for better layer caching
RUN dnf install -y gcc gcc-c++ python3-devel && dnf clean all

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy application files
COPY . ${LAMBDA_TASK_ROOT}/

RUN ln -s ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}/backend

# Set Python path to include both the task root and the backend directory
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}:${LAMBDA_TASK_ROOT}/backend"

# Add health check
HEALTHCHECK CMD exit 0

# Change ownership and switch to non-root user
RUN chown -R appuser:appuser ${LAMBDA_TASK_ROOT}
USER appuser

CMD ["main_handler.handler"]
