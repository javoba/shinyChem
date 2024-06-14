
# About this Shiny Server

The purpose of this Shiny server is to make code easily accessible to users without requiring any programming skills or the need to install any software locally. This server hosts a variety of applications written in Python and R, providing tools for data analysis, visualizations or simulations.

# How this Server Works

This server is hosted using Docker. Docker is an open-source platform that simplifies the deployment and management of applications through containerization. Containers bundle an application and its dependencies into a single package.

Every program of this server is built in its own dedicated Docker container.

For information on how to install Docker, see [https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/).

Once docker containers are installed, they can be accessed in a browser using the address `<local IP of the host>:<port>` when accessing from a different PC (has to be in the same local network), or `localhost:<port>` on the Host itself.

## Create Docker Container

Individual Docker containers can be created by creating a new directory in `~/docker/shiny/` that contains your Code as well as a Dockerfile (i.e. a file named `Dockerfile` without any file extension).

The content of this Dockerfile depends on the programming language, as well as on the packages required by the code:

### Python

For Python, the required libraries can either be provided in a `requirements.txt` file, or directly specified in the Dockerfile. This is an example of a Dockerfile for a python Shiny application:

```bash
FROM python:3.12

COPY ./requirements.txt .
RUN pip3 install -r requirements.txt
WORKDIR /app

EXPOSE 8080

COPY ./<Name of Python file>.py ./

CMD ["uvicorn", "<Python file>
", "--host", "0.0.0.0", "--port", "8080"]
```

This part:
```bash
COPY ./requirements.txt .
RUN pip3 install -r requirements.txt
```

Can be replaced by specifying the required packages directly:
```bash
RUN pip3 install shiny plotly …
```


### R

This is an example of a Dockerfile for a Shiny application written in R:

```bash
FROM rocker/shiny
RUN mkdir /home/shiny-app

RUN R -e "install.packages(c('plotly', 'shiny', …))"

COPY <Name of R file>.R /home/shiny-app/app.R

EXPOSE 8180

CMD ["R", "-e", "shiny::runApp('/home/shiny-app/app.R', host='0.0.0.0', port=8180)"]
```


## Deploy Docker Container

To deploy the Docker container, change directory to the folder of the Docker container and run these commands in a terminal:

```bash
docker kill <name of Docker container>
docker container prune -f
docker build -t <author>/<name of Docker container> .
docker run -d -p <port of Docker container>:8080 --restart unless-stopped --name <name of Docker container> <author>/<name of Docker container>
```

The first two lines are only necessary when the Docker is updated, not when it is created for the first time.

The port and name of the Docker container can be chosen freely, as long as they are not already taken by something else.

It is recommended to save these commands as a bash script (e.g. redeploy.sh) for easier (re)deployment of the Docker container.

## Create SSL Certificate

To make the code accessible from a domain using a valid SSL certificate, the instructions from [this YouTube video](https://www.youtube.com/watch?v=qlcVx-k-02E) were followed:

Note that this only has to be done once when the server is initially deployed, afterwards the certificate *should* renew itself automatically.

- Create a DuckDNS account under [http://www.duckdns.org/](http://www.duckdns.org/) and add a new Domain using the local IP address of the host PC.
- Install and login to Nginx Proxy Manager as described in [https://nginxproxymanager.com/guide/](https://nginxproxymanager.com/guide/)
- Go to "SSL Certificates" and add a new SSL Certificate with Let's Encrypt:
  - Add the domain chosen in DuckDNS, as well as subdomains: `*.<DuckDNS domain>.duckdns.org`, `<DuckDNS domain>.duckdns.org,`
  - Check "Use a DNS Challenge", choose DuckDNS and add the token from your DuckDNS account.
  - Increase the Propagation seconds to 120 and click Save

## Create Proxy Host for Docker Container

With the SSL certificate, subdomains can now be added for each of the Docker containers:

- In Nginx Proxy Manager go to Hosts -> Proxy Hosts and add a proxy host
- Choose the desired subdomain of the docker container (e.g. for the Nginx Proxy Manager Docker container enter `nginx.<DuckDNS domain>.duckdns.org`)
- Add the hostname (can be the local IP or the full chosen DuckDNS domain) and port of the Docker container (e.g. 81 for nginx Proxy Manager)
- Check the boxes underneath (especially the Websockets support needs to enabled for Shiny apps)
- Add the SSL certificate in the SSL tab and check the boxes
- Click Save

The new Docker container is now accessible under the chosen subdomain with a valid SSL certificate.

## Update Docker Containers
If there are changes made to the code in the [GitLab Repository](https://gitlab.empa.ch/vbja/shinychem), they can be downloaded and implemented by running `python3 update.py` in the `shinychem/` directory of the Host.

This requires the connection to the repository to be set, so that the changes can be pulled.
