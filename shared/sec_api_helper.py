# sec_api_helper.py
# 最后修改时间：2025-06-25
# 功能：通过 SEC API 稳定构建 XML 文件真实下载链接

from urllib.parse import urlparse

class SecApiHelper:
    @staticmethod
    def extract_accession_info(html_url):
        """
        从 HTML URL 提取 CIK + accession 编号（去除 index.html 后缀）
        示例：https://www.sec.gov/Archives/edgar/data/1234567/0001234567-24-000123/index.html
        """
        try:
            parsed = urlparse(html_url)
            parts = parsed.path.split('/')
            cik = parts[4]  # data/1234567
            accession = parts[5].replace("-index.html", "")
            return cik, accession
        except:
            return None, None

    @staticmethod
    def construct_xml_url(html_url):
        """
        将 HTML 页面 URL 构造成 XML 文件下载地址
        """
        cik, accession = SecApiHelper.extract_accession_info(html_url)
        if not cik or not accession:
            return None

        acc_no_nodash = accession.replace('-', '')
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_nodash}/{accession}.xml"
        return xml_url
