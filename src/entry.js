const http = require("http");
const fs = require("fs");
const path = require("path");

const contentTypes = {
    ".css": "text/css",
    ".html": "text/html",
    ".js": "text/javascript",
    ".ttf": "font/ttf"
};

const server = http.createServer((req, res) => {
    const requestPath = new URL(req.url, "http://localhost").pathname;
    const file = requestPath.startsWith("/assets/")
        ? path.join(__dirname, requestPath)
        : path.join(__dirname, "ui", requestPath === "/" ? "index.html" : requestPath);

    fs.readFile(file, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end("404");
            return;
        }

        res.writeHead(200, {
            "Content-Type": contentTypes[path.extname(file)] || "application/octet-stream"
        });
        res.end(data);
    });
});

server.listen(3000, "127.0.0.1", () => {
    console.log("running at http://localhost:3000");
});