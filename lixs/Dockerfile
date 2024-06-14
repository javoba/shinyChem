FROM python:3.12

COPY ./requirements.txt .
RUN pip3 install -r requirements.txt
WORKDIR /app

EXPOSE 8080

COPY ./hack.css ./nist_lines.pkl lixs_spectrum.py ./

CMD ["uvicorn", "lixs_spectrum:app", "--host", "0.0.0.0", "--port", "8080"]
