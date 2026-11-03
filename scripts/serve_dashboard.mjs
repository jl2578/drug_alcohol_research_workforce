// SPDX-License-Identifier: MIT
// Development/test server for the public curated repository only.
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {realpath, stat} from 'node:fs/promises';
import {dirname, extname, isAbsolute, relative, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = await realpath(resolve(dirname(fileURLToPath(import.meta.url)), '..'));
const prefix = '/drug_alcohol_research_workforce/';
const port = Number(process.env.DASHBOARD_TEST_PORT ?? 8124);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid preview port');
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
  '.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.json':'application/json; charset=utf-8','.csv':'text/csv; charset=utf-8',
  '.txt':'text/plain; charset=utf-8','.md':'text/plain; charset=utf-8',
  '.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.pdf':'application/pdf',
  '.zip':'application/zip','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'};
const inside = path => {const rel = relative(root,path); return !isAbsolute(rel) && rel !== '..' && !rel.startsWith('..'+sep);};
const server = createServer(async (request,response) => {
  const reject = (status,message) => {response.writeHead(status,{'Content-Type':'text/plain; charset=utf-8'});response.end(message);};
  if (!['GET','HEAD'].includes(request.method)) return reject(405,'GET or HEAD required');
  try {
    const url = new URL(request.url,'http://127.0.0.1');
    const pathname = decodeURIComponent(url.pathname);
    if (!pathname.startsWith(prefix)) return reject(404,'Not found');
    const rel = pathname.slice(prefix.length);
    if (rel.includes('\\') || rel.includes('\0') || rel.split('/').some(part=>part.startsWith('.'))) return reject(403,'Forbidden path');
    let path = resolve(root,rel);
    if (!inside(path)) return reject(403,'Forbidden path');
    if ((await stat(path)).isDirectory()) {
      if (!pathname.endsWith('/')) {
        response.writeHead(302,{Location:pathname+'/'+url.search});response.end();return;
      }
      path = resolve(path,'index.html');
    }
    path = await realpath(path);
    if (!inside(path)) return reject(403,'Forbidden path');
    const info = await stat(path);
    if (!info.isFile()) return reject(404,'Not found');
    response.writeHead(200,{'Content-Type':mime[extname(path).toLowerCase()]??'application/octet-stream',
      'Content-Length':info.size,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
    if (request.method==='HEAD') {response.end();return;}
    createReadStream(path).on('error',()=>response.destroy()).pipe(response);
  } catch(error) {
    if (!response.headersSent) reject(error instanceof URIError?400:404,'Not found');
    else response.destroy();
  }
});
server.listen(port,'127.0.0.1',()=>process.stdout.write(`Dashboard preview: http://127.0.0.1:${port}${prefix}dashboard/\n`));
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>server.close(()=>process.exit(0)));
