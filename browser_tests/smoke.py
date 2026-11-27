"""Optional real-browser smoke test. python -m pip install playwright; playwright install chromium."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(root)))
thread=Thread(target=server.serve_forever,daemon=True);thread.start()
origin=f'http://127.0.0.1:{server.server_port}'
try:
    with sync_playwright() as p:
        path=os.environ.get('PBK_CHROMIUM_EXECUTABLE')
        browser=p.chromium.launch(**({'executable_path':path} if path else {}))
        page=browser.new_page()
        errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:requests.append((req.method,req.url)))
        page.goto(origin+'/web/')
        page.locator('h1').filter(has_text='Upload-Größenprüfung').wait_for()
        page.locator('#files').set_input_files([
            {'name':'合同_é.pdf','mimeType':'application/pdf','buffer':b'x'*5_000_000},
            {'name':'ملف_😀.pdf','mimeType':'application/pdf','buffer':b'x'*5_000_001}])
        assert page.locator('#results .ok').count()==1
        assert page.locator('#results .bad').count()==1
        assert 'ملف_😀.pdf' in page.locator('#results .bad').inner_text()
        page.locator('#locale').select_option('ar')
        assert page.locator('html').get_attribute('dir')=='rtl'
        assert 'ميغابايت' in page.locator('#results .bad').inner_text()
        page.locator('#enabled').uncheck()
        assert page.locator('#results .bad').count()==0
        assert page.locator('#results li').count()==2
        page.locator('#enabled').check()
        page.locator('#locale').select_option('en')
        assert page.locator('html').get_attribute('dir')=='ltr'
        # Actual DOM drag/drop handler via browser DataTransfer, not an OS-level drag.
        page.locator('#drop').evaluate("""el => {const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(5000001)],'drop_合同.pdf'));el.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));}""")
        assert 'drop_合同.pdf' in page.locator('#results .bad').inner_text()
        assert '5 MB' in page.locator('#results .bad').inner_text()
        page.locator('#limit').fill('6')
        assert page.locator('#results .ok').count()==1
        page.locator('#limit').fill('0')
        assert 'positive' in page.locator('#results .bad').inner_text()
        assert not errors, errors
        assert all(method=='GET' and url.startswith(origin+'/') for method,url in requests),requests
        browser.close()
        print('Browser smoke passed: file input, boundary, locale/RTL, disabled check, DOM drop, limits, no uploads.')
finally:
    server.shutdown();server.server_close();thread.join()
