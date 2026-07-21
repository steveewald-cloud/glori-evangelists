// Minimal zero-dependency static server for the GLORi commission prototype.
const http = require('http');
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'));
const port = process.env.PORT || 8080;
http.createServer((req, res) => {
  if (req.url === '/health') { res.writeHead(200); return res.end('ok'); }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
}).listen(port, '0.0.0.0', () => console.log('GLORi commission prototype on :' + port));
