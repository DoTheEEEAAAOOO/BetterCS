const http = require("http");
const fs = require("fs");
const path = require("path");

const server = http.createServer((req, res) => {
    const file = req.url === "/"
        ? path.join(__dirname, "ui", "index.html")
        : path.join(__dirname, "ui", req.url);

    fs.readFile(file, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end("404");
            return;
        }

        res.writeHead(200, {
            "Content-Type": "text/html"
        });
        res.end(data);
    });
});

server.listen(3000, "127.0.0.1", () => {
    console.log("running at http://localhost:3000");
});