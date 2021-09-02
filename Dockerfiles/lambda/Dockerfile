FROM lambci/lambda:build-python3.7
# or, if choosing to use a container pre-built with numpy:
# FROM AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/PROJECT-dashboard-api-base:TAG

WORKDIR /app

COPY README.md /app/README.md
COPY dashboard_api/ /app/dashboard_api/
COPY setup.py /app/setup.py

RUN pip install --upgrade pip && \
    pip install . "mangum>=0.9.0,<0.10.1" -t /var/task --no-binary numpy,pydantic && \
    cd /var/task && find . -type f -name '*.pyc' | while read f; do n=$(echo $f | sed 's/__pycache__\///' | sed 's/.cpython-[2-3][0-9]//'); cp $f $n; done; \
    cd /var/task && find . -type d -a -name '__pycache__' -print0 | xargs -0 rm -rf && \
    cd /var/task && find . -type f -a -name '*.py' -print0 | xargs -0 rm -f && \
    find /var/task -type d -a -name 'tests' -print0 | xargs -0 rm -rf && \
    echo "Remove lambda python packages" && \
    rm -rdf /var/task/numpy/doc/  && \
    rm -rdf /var/task/stack && \
    rm -rdf /var/task/boto3* && \
    rm -rdf /var/task/botocore* && \
    rm -rdf /var/task/docutils* && \
    rm -rdf /var/task/dateutil* && \
    rm -rdf /var/task/jmespath* && \
    rm -rdf /var/task/s3transfer*

RUN mkdir /var/task/stack
COPY stack/config.yml /var/task/stack/config.yml
COPY lambda/handler.py /var/task/handler.py
