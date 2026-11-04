"""Live HTTP, Next.js proxy and Chromium test: does not mock backend."""
import json
import re
import urllib.request
from playwright.sync_api import sync_playwright, expect


def fetch_json(path, data=None, method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request("http://127.0.0.1:3000/api"+path,
        data=body,
        method=method or ("POST" if data is not None else "GET"),
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def api_checks():
    health=fetch_json("/health")
    assert health["status"]=="ok", health
    ds=fetch_json("/datasets/demo", data={})
    assert ds["rows"]>=20 and ds["kpis"]["total_revenue"]>0, ds
    question=fetch_json("/questions",{"dataset_id":ds["id"],"question":"What is total revenue?"})
    assert question["status"]=="completed", question
    report=fetch_json("/tasks",{"dataset_id":ds["id"],"prompt":"Analyze business performance"})
    assert report["verification"]["approved"] is True, report
    with urllib.request.urlopen("http://127.0.0.1:3000/api/tasks/"+report["id"]+"/export",timeout=20) as response:
        html=response.read().decode("utf-8")
    assert "html" in html.lower() and "الإيرادات" in html, html[:300]
    print("PASS real Next.js proxy, FastAPI demo dataset, evidence-backed question, tasks, HTML report")


def browser_checks():
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        page=browser.new_page(viewport={"width":1440,"height":950})
        page.on("pageerror",lambda exc: errors.append(str(exc)))
        page.goto("http://localhost:3000/",wait_until="domcontentloaded",timeout=60000)
        expect(page.get_by_role("navigation",name="التنقل الرئيسي")).to_be_visible(timeout=20000)
        page.get_by_role("button",name=re.compile("افتح مساحة البيانات")).first.click()
        page.get_by_role("button",name="جرّب بيانات نموذجية").click()
        expect(page.get_by_text("demo-sales.csv").first).to_be_visible(timeout=30000)
        page.get_by_role("button",name=re.compile("الذكاء")).first.click()
        page.get_by_role("button",name=re.compile("شغّل التحليل")).first.click()
        expect(page.get_by_text("تقرير الذكاء الإداري").first).to_be_visible(timeout=30000)
        if errors:
            raise AssertionError("Uncaught browser errors:\n"+"\n".join(errors))
        browser.close()
    print("PASS actual Chromium dashboard demo-data-to-analysis-to-report journey")


if __name__=="__main__":
    api_checks()
    browser_checks()
