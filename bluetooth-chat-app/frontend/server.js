const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const port = Number(process.env.PORT || 3000);

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "bluetooth-chat-frontend" });
});

// Render / config support:
// Render provides a backend URL at runtime; we inject it into index.html.
app.get("/", (_req, res) => {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  const indexPath = path.join(__dirname, "public", "index.html");
  const html = fs.readFileSync(indexPath, "utf8");
  res.send(html.replaceAll("__BACKEND_URL__", backendUrl));
});

app.use(express.static(path.join(__dirname, "public")));

app.listen(port, () => {
  console.log(`Frontend running at http://localhost:${port}`);
});
