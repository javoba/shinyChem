docker kill calibration
docker container prune -f
docker build -t javoba/calibration .
docker run -d -p 8054:8080 --restart unless-stopped --name calibration javoba/calibration
