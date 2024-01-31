# Global imports
import logging

import requests

from easyeda2kicad import __version__
from bs4 import BeautifulSoup


API_ENDPOINT_PARAMETERS = "https://easyeda.com/api/eda/product/search?version=6.5.39&keyword={lcsc_id}&needAggs=true&needComponents=true"

API_ENDPOINT = "https://easyeda.com/api/products/{lcsc_id}/components?version=6.4.19.5"
ENDPOINT_3D_MODEL = "https://easyeda.com/analyzer/api/3dmodel/{uuid}"
# ------------------------------------------------------------


class EasyedaApi:
    def __init__(self) -> None:
        self.headers = {
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": f"easyeda2kicad v{__version__}",
        }

    def get_info_from_easyeda_api(self, lcsc_id: str) -> dict:
        r = requests.get(url=API_ENDPOINT.format(lcsc_id=lcsc_id), headers=self.headers)
        api_response = r.json()

        if not api_response or (
            "code" in api_response and api_response["success"] is False
        ):
            logging.debug(f"{api_response}")
            return {}

        return r.json()

    def get_cad_data_of_component(self, lcsc_id: str) -> dict:
        cp_cad_info = self.get_info_from_easyeda_api(lcsc_id=lcsc_id)
        if cp_cad_info == {}:
            return {}

       # Get parameters data
        params_response = requests.get(url=API_ENDPOINT_PARAMETERS.format(lcsc_id=lcsc_id), headers=self.headers)
        params_data = params_response.json()

        if "result" in params_data and "paramList" in params_data["result"]:
            parameters = params_data["result"]["paramList"]
            parameters_obj = {param["parameterName"]: ', '.join(param["parameterValueList"]) for param in parameters}
            cp_cad_info["result"]["parameters"] = parameters_obj
        else:
            cp_cad_info["result"]["parameters"] = []

        # Get product description
        description_url = f"https://www.lcsc.com/product-detail/{lcsc_id}.html"
        description_page = requests.get(description_url)
        soup = BeautifulSoup(description_page.content, 'html.parser')

        description = self.parse_description(soup)
        cp_cad_info["result"]["description"] = description

        return cp_cad_info["result"]

    def parse_description(self, soup: BeautifulSoup) -> str:
        description_tag = soup.find('td', text='Description')
        if description_tag and description_tag.find_next_sibling('td'):
            return description_tag.find_next_sibling('td').get_text(strip=True)
        return ""

    def get_raw_3d_model_obj(self, uuid: str) -> str:
        r = requests.get(
            url=ENDPOINT_3D_MODEL.format(uuid=uuid),
            headers={"User-Agent": self.headers["User-Agent"]},
        )
        if r.status_code != requests.codes.ok:
            logging.error(f"No 3D model data found for uuid:{uuid} on easyeda")
            return None
        return r.content.decode()
