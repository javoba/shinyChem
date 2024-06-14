docker kill xanes-cs
docker container prune -f
docker build -t vbja/xanes-cs .
docker run -d -p 8058:8080 --restart unless-stopped --name xanes-cs vbja/xanes-cs
