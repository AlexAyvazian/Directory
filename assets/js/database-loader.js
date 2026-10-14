(async function loadDirectory(){
 const label=document.getElementById('mapLabel');label.textContent='Loading directory…';
 try{
  const response=await fetch('/api/atlas',{cache:'no-store'});
  if(!response.ok)throw new Error('Directory unavailable');
  const data=await response.json();
  if(!Array.isArray(data.states)||!Array.isArray(data.jurisdictions))throw new Error('Invalid directory data');
  window.ATLAS_DATA=data;
  const script=document.createElement('script');script.src='assets/js/app.js';document.body.appendChild(script);
 }catch(e){
  label.textContent='Directory could not load. Please retry.';
  document.getElementById('loading').hidden=true;
  const retry=document.createElement('button');retry.type='button';retry.textContent='Retry';retry.onclick=()=>location.reload();label.appendChild(retry);
 }
})();
