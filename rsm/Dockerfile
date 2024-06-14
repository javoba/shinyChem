FROM python:3.12

RUN pip3 install shinywidgets numpy pandas plotly
WORKDIR /app

EXPOSE 8080

COPY ./hack.css ./rsm.py ./

CMD ["uvicorn", "rsm:app", "--host", "0.0.0.0", "--port", "8080"]
