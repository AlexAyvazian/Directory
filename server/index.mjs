import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import pg from 'pg';
import {composeAtlas} from './data.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
if(!process.env.DIRECTORY_DATABASE) throw new Error('DIRECTORY_DATABASE is required');
const pool=new pg.Pool({connectionString:process.env.DIRECTORY_DATABASE,max:3,connectionTimeoutMillis:15000,idleTimeoutMillis:30000});
pool.on('error',()=>console.error('Database pool connection failed'));
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.ico':'image/x-icon'};
export const server=http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
  if(url.pathname==='/healthz'){await pool.query('SELECT 1');res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({status:'ok',database:'Neon'}));return;}
  if(url.pathname==='/api/atlas'){
   const client=await pool.connect();let atlas;
   try {
    await client.query('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');
    const meta=await client.query("SELECT data FROM directory_metadata WHERE key='atlas'");
    if(!meta.rows.length)throw new Error('Directory import required');
    const jurisdictions=await client.query('SELECT data FROM directory_jurisdictions ORDER BY id');
    const contacts=await client.query('SELECT * FROM directory_contacts ORDER BY id');
    atlas=composeAtlas(meta.rows[0].data,jurisdictions.rows.map(r=>r.data),contacts.rows);
    await client.query('COMMIT');
   } catch(e){await client.query('ROLLBACK');throw e;}finally{client.release();}
   res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(atlas));return;
  }
  // Only expose the app shell and presentation assets. Source data and credentials stay server-side.
  const p=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));
  if(p!=='index.html' && !/^assets\/(css|js|vendor)\/[\w.-]+$/.test(p)){res.writeHead(404);res.end('Not found');return;}
  if(/atlas-data|registry-|fl-association/.test(p)){res.writeHead(404);res.end('Not found');return;}
  const data=await readFile(path.join(root,p));res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Cache-Control':'no-cache'});res.end(req.method==='HEAD'?undefined:data);
 }catch(e){res.writeHead(e.code==='ENOENT'?404:503,{'Content-Type':'application/json'});res.end(JSON.stringify({error:e.code==='ENOENT'?'Not found':'Directory temporarily unavailable. Please retry.'}));console.error('Directory request failed',e.code||e.name);}
});
server.listen(Number(process.env.PORT||3000),'0.0.0.0',()=>console.log('Directory server ready'));
process.on('SIGTERM',()=>server.close(()=>pool.end()));
