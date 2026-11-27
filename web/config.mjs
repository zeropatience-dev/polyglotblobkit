import {validateFiles} from './upload-limiter.mjs';
const defaults = Object.freeze({ui_limiter:true,backend_limiter:true,legacy_support:true});
function checkObject(value,allowed) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(k=>!allowed.includes(k))) throw new TypeError('Invalid configuration fields');
}
export function parseConfig(data={}) {
  checkObject(data,['version','max_upload_mb','locale','modules']);
  const {version=1,max_upload_mb=50,locale='en',modules={}}=data;
  if (version!==1) throw new RangeError('Unsupported configuration version');
  validateFiles([],max_upload_mb);
  if (typeof locale!=='string' || !locale.trim()) throw new TypeError('Invalid locale');
  checkObject(modules,Object.keys(defaults));
  const flags={...defaults,...modules};
  if (Object.values(flags).some(v=>typeof v!=='boolean')) throw new TypeError('Module flags must be booleans');
  return Object.freeze({version,max_upload_mb,locale,modules:Object.freeze(flags)});
}
export function validateConfiguredFiles(files, data={}) {
  const config=parseConfig(data);
  const input=Array.from(files);
  const result=validateFiles(input,config.max_upload_mb);
  if (config.modules.ui_limiter) return {...result,checked:true};
  // Preserve input order even when the size check is disabled.
  return {accepted:input,rejected:[],maxBytes:result.maxBytes,checked:false};
}
