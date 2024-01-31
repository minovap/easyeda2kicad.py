# Global imports
import logging
import re
import json5
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
        #params_response = requests.get(url=API_ENDPOINT_PARAMETERS.format(lcsc_id=lcsc_id), headers=self.headers)
        #params_data = params_response.json()

        #if "result" in params_data and "paramList" in params_data["result"]:
        #    parameters = params_data["result"]["paramList"]
        #    parameters_obj = {param["parameterName"]: ', '.join(param["parameterValueList"]) for param in parameters}
        #    cp_cad_info["result"]["parameters"] = parameters_obj
        #else:
        #    cp_cad_info["result"]["parameters"] = []

        # Get product description
        description_url = f"https://www.lcsc.com/product-detail/{lcsc_id}.html"
        description_page = requests.get(description_url)
        soup = BeautifulSoup(description_page.content, 'html.parser')

        description = self.parse_description(soup)
        cp_cad_info["result"]["description"] = description


        # Extract the script tag containing 'window.__NUXT__' using BeautifulSoup
        nuxt_script_tag = soup.find('script', text=re.compile('window.__NUXT__'))

        # Trim the script content to start from the second '{' and remove '));' at the end
        trimmed_script_content = re.sub(r'^.*?\{.*?\{', '{', nuxt_script_tag.string, count=1, flags=re.DOTALL)
        trimmed_script_content = re.sub(r'\)\);\s*$', '', trimmed_script_content, flags=re.DOTALL)

        # Split the trimmed content into two parts at the last '}{'
        script_parts = trimmed_script_content.rsplit('}(', 1);

        # The first part is the main JSON structure
        main_json_structure = script_parts[0]
        main_json_structure = script_parts[0]

        # The second part is an array of values used in the main JSON structure
        value_array_str = '[' + script_parts[1] + ']'
        value_array = json5.loads(value_array_str)

        # Replace placeholders (like :a, :b, :c, ...) in the main JSON structure with actual values from the array
        for index, letter in enumerate("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            if index < len(value_array):
                replacement_value = '"' + str(value_array[index]) + '"'  # Convert value to a string with quotes
                main_json_structure = main_json_structure.replace(f':{letter}', f':{replacement_value}')

        component_data = json5.loads(main_json_structure)
        parameter_data = component_data['data'][0]['detail']['paramVOList']
        # Convert the list of dictionaries into a dictionary with 'paramNameEn' as keys and 'paramValueEn' as values
        parameters_en_dict = {param['paramNameEn']: param['paramValueEn'] for param in parameter_data}

        parameters_en_dict["Category"] = self.parse_category(soup)

        # Set the value for resistor components
        category_value_map = {
            "Resistor": "Resistance",
            "Capacitor": "Capacitance",
            "Inductor": "Inductance"
        }

        category = parameters_en_dict.get("Category", "")

        for cat, value_field in category_value_map.items():
            if cat in category:
                parameters_en_dict["Value"] = parameters_en_dict.get(value_field, "")
                break

        parameters_en_dict["Package"] = self.parse_package_value(soup)
        cp_cad_info["result"]["parameters"] = parameters_en_dict

        return cp_cad_info["result"]

    def parse_attributes(self, soup: BeautifulSoup) -> dict:
        attributes = {}
        rows = soup.select('table.products-specifications tbody tr')
        for row in rows:
            print(row.get_text(separator=' | ', strip=True))
        for row in rows:
            attribute_name = row.find('td').get_text(strip=True)

            attribute_value = row.find_all('td')[1].get_text(strip=True)
            attributes[attribute_name] = attribute_value
            print(attribute_value)

        return attributes

    def parse_package_value(self, soup: BeautifulSoup) -> str:
        package_tag = soup.find('td', text='Package')
        if package_tag and package_tag.find_next_sibling('td'):
            return package_tag.find_next_sibling('td').get_text(strip=True)
        return ""

    def parse_description(self, soup: BeautifulSoup) -> str:
        description_tag = soup.find('td', text='Description')
        if description_tag and description_tag.find_next_sibling('td'):
            return description_tag.find_next_sibling('td').get_text(strip=True)
        return ""

    def parse_category(self, soup: BeautifulSoup) -> str:
        breadcrumbs = soup.select('.v-breadcrumbs__item')
        if breadcrumbs:
            return breadcrumbs[-2].get_text(strip=True)
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
