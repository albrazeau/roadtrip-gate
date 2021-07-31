FROM tiangolo/uwsgi-nginx-flask:python3.8

COPY ./ /app

RUN pip install -r /app/requirements.txt
RUN chmod +x /app/run_all.sh