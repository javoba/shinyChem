FROM python:3.12

COPY ./requirements.txt .
RUN pip3 install -r requirements.txt
WORKDIR /app

EXPOSE 8080

COPY ./hack.css heatmap.py ./
ADD LiF LiF
ADD Al Al
ADD Ni Ni

CMD ["uvicorn", "heatmap:app", "--host", "0.0.0.0", "--port", "8080"]
