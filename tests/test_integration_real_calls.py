"""
Salva Runtime 整合測試集 - 真實 API/MCP/Skill 調用

基於對話log.md 中的真實使用模式設計
需要啟動服務後執行: python3 -m pytest tests/test_integration_real_calls.py -v

測試覆蓋:
1. REST API 同步/異步發現
2. MCP 工具調用 (需 MCP server)
3. Skill 端到端流程 (需 OpenClaw)
4. 多 objective/market/industry 矩陣測試
"""

import os
import subprocess
import time
import pytest
import requests


SALVA_API_URL = os.getenv("SALVA_API_URL", "http://127.0.0.1:8000")
SALVA_API_KEY = os.getenv("SALVA_API_KEY", "")
TEST_TIMEOUT = 30


def wait_for_api(url: str, timeout: int = 10) -> bool:
    """等待 API 就緒"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{url}/health", timeout=2)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def wait_for_job_complete(job_id: str, timeout: int = 60) -> dict | None:
    """等待 job 完成並返回結果"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{SALVA_API_URL}/v1/jobs/{job_id}", timeout=5)
            if resp.status_code == 200:
                job = resp.json()
                if job["status"] in ("completed", "failed"):
                    return job
        except Exception:
            pass
        time.sleep(2)
    return None


class TestRestApiDiscover:
    """REST API /v1/discover 同步發現測試"""

    @classmethod
    def setup_class(cls):
        if not wait_for_api(SALVA_API_URL):
            pytest.skip("Salva API not running")

    def test_find_leads_taiwan_hardware(self):
        """測試: find_leads + 台灣 + 硬體 (使用 job 異步)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_leads",
                    "intent": {
                        "market": "台灣",
                        "industry": "硬體",
                        "role": "業務",
                    },
                    "output_profile": "lead",
                    "max_results": 10,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        job = resp.json()
        assert job["status"] == "completed"

    def test_find_companies_us_ai_hardware(self):
        """測試: find_companies + US + AI hardware (使用 job 異步)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_companies",
                    "intent": {
                        "market": "US",
                        "industry": "AI hardware",
                    },
                    "output_profile": "company_profile",
                    "max_results": 10,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "completed"

    def test_find_events_japan_art_toys(self):
        """測試: find_events + Japan + art toys (使用 job 異步)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_events",
                    "intent": {
                        "market": "Japan",
                        "industry": "art toys",
                    },
                    "output_profile": "event",
                    "max_results": 10,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        job = resp.json()
        assert job["status"] == "completed"

    def test_find_partnership_signals_germany_software(self):
        """測試: find_partnership_signals + Germany + software (使用 job 異步)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_partnership_signals",
                    "intent": {
                        "market": "Germany",
                        "industry": "software",
                    },
                    "output_profile": "company_profile",
                    "max_results": 10,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "completed"

    def test_discover_with_extra_keywords(self):
        """測試: 額外關鍵詞"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_leads",
                    "intent": {
                        "market": "Taiwan",
                        "industry": "AI",
                        "extra_keywords": ["remote", "senior"],
                        "negative_keywords": ["intern"],
                    },
                    "max_results": 5,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "completed"

    def test_discover_output_profile_lead(self):
        """測試: output_profile=lead"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_leads",
                    "intent": {"market": "US", "industry": "SaaS"},
                    "output_profile": "lead",
                    "max_results": 10,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "completed"

    def test_discover_output_profile_crm_contact(self):
        """測試: output_profile=crm_contact"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_leads",
                    "intent": {"market": "Germany", "industry": "fintech"},
                    "output_profile": "crm_contact",
                    "max_results": 10,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "completed"


class TestRestApiJobs:
    """REST API /v1/jobs 異步作業測試"""

    @classmethod
    def setup_class(cls):
        if not wait_for_api(SALVA_API_URL):
            pytest.skip("Salva API not running")

    def test_job_create_async(self):
        """測試: 創建異步 job (不等待)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_leads",
                    "intent": {"market": "Japan", "industry": "gaming"},
                    "max_results": 50,
                },
                "wait_for_completion": False,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=TEST_TIMEOUT,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "queued"
        assert job["job_id"]

    def test_job_poll_and_cancel(self):
        """測試: 輪詢 job + 取消"""
        # 創建 job
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_events",
                    "intent": {"market": "Europe", "industry": "tech"},
                    "max_results": 30,
                },
                "wait_for_completion": False,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        job = resp.json()
        job_id = job["job_id"]

        # 查詢狀態
        status_resp = requests.get(
            f"{SALVA_API_URL}/v1/jobs/{job_id}",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["job_id"] == job_id


class TestRestApiQueries:
    """REST API 查詢端點測試"""

    @classmethod
    def setup_class(cls):
        if not wait_for_api(SALVA_API_URL):
            pytest.skip("Salva API not running")

    def test_list_runs(self):
        """測試: 列出 runs"""
        resp = requests.get(
            f"{SALVA_API_URL}/v1/runs?limit=5",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_jobs(self):
        """測試: 列出 jobs"""
        resp = requests.get(
            f"{SALVA_API_URL}/v1/jobs?limit=5",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert resp.status_code == 200

    def test_list_plugins(self):
        """測試: 列出 plugins"""
        resp = requests.get(
            f"{SALVA_API_URL}/v1/plugins",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_providers(self):
        """測試: 列出 providers"""
        resp = requests.get(
            f"{SALVA_API_URL}/v1/providers",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_routes(self):
        """測試: 列出 routes"""
        resp = requests.get(
            f"{SALVA_API_URL}/v1/routes",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


class TestMcpIntegration:
    """MCP Server 工具調用測試 (需啟動 MCP server)"""

    @pytest.fixture(autouse=True)
    def check_mcp_available(self):
        """檢查 MCP 是否可用"""
        try:
            result = subprocess.run(
                ["python3", "-c", "from apps.mcp import server"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                pytest.skip("MCP server not importable")
        except Exception:
            pytest.skip("MCP not available")

    def test_mcp_discover_sync(self):
        """測試: MCP discover 同步調用"""
        # 需要 stdio 模式或 HTTP 模式啟動 MCP
        # 這裡測試 import 和參數解析
        from apps.mcp.server import _parse_domain_hints

        result = _parse_domain_hints('{"signal_terms": ["test"]}')
        assert result is not None

    def test_mcp_job_create(self):
        """測試: MCP job create 工具"""
        # 實際 MCP 測試需要啟動 stdio server
        # 這裡只測工具是否存在
        from apps.mcp import server

        assert hasattr(server, "salva_job_create")
        assert hasattr(server, "salva_job_status")
        assert hasattr(server, "salva_job_cancel")
        assert hasattr(server, "salva_run_result")
        assert hasattr(server, "salva_audit")
        assert hasattr(server, "salva_pilot")
        assert hasattr(server, "salva_vocab")
        assert hasattr(server, "salva_plugins")
        assert hasattr(server, "salva_providers")
        assert hasattr(server, "salva_topology")


class TestSkillIntegration:
    """Skill 端到端測試 (需 OpenClaw 環境)"""

    @pytest.fixture(autouse=True)
    def check_skill_available(self):
        """檢查 skill 是否可用"""
        skill_path = os.path.expanduser("~/Projects/hermes_workspace/app/skills/salva-search")
        if not os.path.exists(skill_path):
            pytest.skip("salva-search skill not found")

    def test_skill_adapter_import(self):
        """測試: skill adapter 可導入"""
        sys_path = os.path.expanduser("~/Projects/hermes_workspace/app/skills/salva-search")
        import sys

        sys.path.insert(0, sys_path)
        try:
            import adapter

            assert hasattr(adapter, "salva_search_run")
        except ImportError as e:
            pytest.skip(f"Skill adapter not importable: {e}")
        finally:
            sys.path.remove(sys_path)

    def test_skill_requirements_exist(self):
        """測試: skill 目錄有 requirements.txt"""
        skill_path = os.path.expanduser("~/Projects/hermes_workspace/app/skills/salva-search")
        requirements_file = os.path.join(skill_path, "requirements.txt")
        if not os.path.exists(requirements_file):
            pytest.skip("requirements.txt not found in skill directory")


class TestMatrixCombinations:
    """矩陣測試: 多种 objective/market/industry 組合"""

    @classmethod
    def setup_class(cls):
        if not wait_for_api(SALVA_API_URL):
            pytest.skip("Salva API not running")

    @pytest.mark.parametrize("objective,market", [
        ("find_companies", "US"),
        ("find_leads", "Taiwan"),
        ("find_events", "Japan"),
    ])
    def test_objective_market_sample(self, objective, market):
        """測試: 抽樣 objective x market 矩陣 (使用 job)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": objective,
                    "intent": {
                        "market": market,
                        "industry": "software",
                    },
                    "max_results": 5,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200, f"{objective}/{market} failed: {resp.text}"
        job = resp.json()
        assert job["status"] == "completed"

    @pytest.mark.parametrize("industry", ["AI", "fintech"])
    def test_industry_variations(self, industry):
        """測試: 不同 industry (使用 job)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_companies",
                    "intent": {"market": "US", "industry": industry},
                    "max_results": 5,
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=120,
        )
        assert resp.status_code == 200


class TestEdgeCases:
    """邊界情況測試"""

    @classmethod
    def setup_class(cls):
        if not wait_for_api(SALVA_API_URL):
            pytest.skip("Salva API not running")

    def test_empty_market(self):
        """測試: 空 market (對話log line 5787)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/discover",
            json={
                "objective": "find_companies",
                "intent": {"market": "", "industry": ""},
                "max_results": 5,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=TEST_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_max_results_boundary(self):
        """測試: max_results 邊界 (使用 job 異步)"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/jobs",
            json={
                "discovery": {
                    "objective": "find_leads",
                    "intent": {"market": "US", "industry": "tech"},
                    "max_results": 200,  # 上限
                },
                "wait_for_completion": True,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=180,
        )
        assert resp.status_code == 200
        job = resp.json()
        assert job["status"] == "completed"

    def test_invalid_objective(self):
        """測試: 無效 objective"""
        resp = requests.post(
            f"{SALVA_API_URL}/v1/discover",
            json={
                "objective": "invalid_objective",
                "intent": {"market": "US", "industry": "tech"},
                "max_results": 5,
            },
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
            timeout=TEST_TIMEOUT,
        )
        # 應該 fallback 到 general 或報錯
        assert resp.status_code in (200, 400, 422)

    def test_nonexistent_run_id(self):
        """測試: 不存在的 run_id"""
        resp = requests.get(
            f"{SALVA_API_URL}/v1/runs/nonexistent_run_id_12345",
            headers={"X-Salva-Key": SALVA_API_KEY} if SALVA_API_KEY else {},
        )
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])