FROM public.ecr.aws/lambda/python:3.12-x86_64

# Install dependencies and create non-root user
RUN dnf install -y shadow-utils gcc gcc-c++ python3-devel && \
    /usr/sbin/useradd -m -u 1001 appuser && \
    dnf clean all

WORKDIR ${LAMBDA_TASK_ROOT}

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
