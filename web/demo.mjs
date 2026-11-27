import {validateConfiguredFiles} from './config.mjs';
import {message,resolveLocale} from './i18n.mjs';
const drop=document.querySelector('#drop'),results=document.querySelector('#results');
const limit=document.querySelector('#limit'),picker=document.querySelector('#files');
const language=document.querySelector('#locale'),enabled=document.querySelector('#enabled');
let selected=[];
function render(files=selected) {
  selected=Array.from(files);results.replaceChildren();
  const locale=resolveLocale(language.value);
  document.documentElement.lang=locale;document.documentElement.dir=locale==='ar'?'rtl':'ltr';
  for(const el of document.querySelectorAll('[data-msg]')) el.textContent=message(el.dataset.msg,locale);
  picker.setAttribute('aria-label',message('DROP',locale));
  function add(file,text,cls) {
    const li=document.createElement('li');li.className=cls;
    if(file){const name=document.createElement('bdi');name.textContent=file.name;li.append(name,document.createTextNode(' — '));}
    li.append(document.createTextNode(text));results.append(li);
  }
  try {
    const policy={max_upload_mb:limit.valueAsNumber,locale,modules:{ui_limiter:enabled.checked}};
    const r=validateConfiguredFiles(selected,policy);
    for(const f of r.accepted) add(f,message(r.checked?'ACCEPTED':'UNCHECKED',locale),r.checked?'ok':'');
    for(const {file,code} of r.rejected) add(file,message(code,locale,{limit:policy.max_upload_mb}),'bad');
  } catch(e) { add(null,message('INVALID_LIMIT',locale),'bad'); }
}
picker.addEventListener('change',()=>render(picker.files));
for(const el of [limit,language,enabled]) el.addEventListener('input',()=>render());
for(const type of ['dragenter','dragover']) drop.addEventListener(type,e=>{e.preventDefault();drop.classList.add('active');});
drop.addEventListener('dragleave',()=>drop.classList.remove('active'));
drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('active');render(e.dataTransfer.files);});
window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('drop',e=>e.preventDefault());
render();
