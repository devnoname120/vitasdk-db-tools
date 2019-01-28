from bs4 import BeautifulSoup as bs
import requests
import regex as re

WIKI_BASE_URL = "https://wiki.henkaku.xyz"
WIKI_MODULES_URL = WIKI_BASE_URL + "/vita/Modules"

C_VALID_IDENTIFIER_REGEX = re.compile(r"^[^\d\W]\w*\Z", re.UNICODE)

def fetch_module_urls():
    print('\n==> Step1: fetch module urls...')

    modules_page = requests.get(WIKI_MODULES_URL)
    modules_soup = bs(modules_page.text, "html.parser")

    module_list = modules_soup.find(id="List_of_Modules")

    # Just extract 3.60 kernel modules right now
    module_tr = module_list.find_next(id="3.60_Kernel_modules").find_next("table").tbody.find_all("tr")

    modules = []

    for module_entry in module_tr:
        # This is the header, skip...
        if module_entry.find('th'):
            continue
        
        link_tag = module_entry.td.find('a')

        # Non-existing wiki page
        if link_tag.has_attr('class') and link_tag['class'][0]  == 'new':
            print("[warning] Module", link_tag.text, "does not have an associated article.")
            continue

        link = WIKI_BASE_URL + link_tag['href']
        name = link_tag.text.strip()

        modules.append((name, link))

    return modules

def extract_nids(modules):
    print('\n==> Step2: fetch module articles...')

    for (name, link) in modules:
        module_page = requests.get(link)
        module_soup = bs(module_page.text, "html.parser")

        # Pages not containing NIDs don't have this
        module_header = module_soup.find(id='Module')
        if not module_header:
            print('[warning] Module', name, 'does not have a module section. Skipping...')
            continue

        library_header = module_soup.find(id='Libraries')
        if not library_header:
            print('[warning] Module', name,
                  'does not have a libraries section. Skipping...')
            continue

        module_table = module_header.find_next(id='Known_NIDs').find_next('table', class_='wikitable')
        module_table_entries =  module_table.tbody.find_all("tr")

        version = 0
        real_name = None
        real_nid = None

        # Check the modules on this module page
        for module_table_entry in module_table_entries:
            bad_header = False

            header = module_table_entry.find_all('th')
            if header:
                expected_headers = ['Version', 'Name', 'World', 'Privilege', 'NID']

                for i, expected in enumerate(expected_headers):
                    got = header[i].text.strip()
                    if got != expected:
                        print('[error] Unexpected module NID table header:', got)
                        bad_header = True

            # Don't process this page if the header is incorrect
            if bad_header:
                print('[error] Skipping module', name, 'because of incorrect header.')
                break

            if header:
                continue

            info = module_table_entry.find_all('td')

            module_version = info[0].text.strip().replace('.', '') # Convert to an int because floats are annoying
            
            # HACK: Firmware range, check if 360 is inside
            if '-' in module_version:
                low, high = module_version.split()
                if int(low) <= 360 <= int(high):
                    module_version = '360'
                else:
                    module_version = high

            module_version = int(module_version)
            
            module_name = info[1].text.strip()
            module_world = info[2].text.strip()
            module_privilege = info[3].text.strip()
            module_nid = info[4].text.strip()

            if module_name != name:
                print('[error] Module name', name, 'does not match its name in NID table', module_name)

            if version != 360:
                version = module_version
                real_nid = module_nid

        if version != 360:
            print('[info] Module', name, 'NID', version, 'instead of 360')



        # Check the libraries on this module page
        library_table = library_header.find_next(id='Known_NIDs_2').find_next('table', class_='wikitable')
        library_table_entries = library_table.tbody.find_all("tr")

        libraries = []

        for library_table_entry in library_table_entries:
            bad_header = False

            header = library_table_entry.find_all('th')
            if header:
                expected_headers = ['Version', 'Name', 'World', 'Visibility', 'NID']

                for i, expected in enumerate(expected_headers):
                    got = header[i].text.strip()
                    if got != expected:
                        print('[error] Unexpected library NID table header:', got)
                        bad_header = True

            # Don't process this page if the header is incorrect
            if bad_header:
                print('[error] Skipping module', name, 'because of incorrect libraries header.')
                break

            if header:
                continue


            info = library_table_entry.find_all('td')

            # Convert to an int because floats are annoying
            library_version = info[0].text.strip().replace('.', '')

            # HACK: Firmware range, check if 360 is inside
            if '-' in library_version:
                low, high = library_version.split('-')
                if int(low) <= 360 <= int(high):
                    library_version = '360'
                else:
                    library_version = high

            library_version = int(library_version)

            library_name = info[1].text.strip()
            library_world = info[2].text.strip()
            library_visibility = info[3].text.strip()
            library_nid = info[4].text.strip()

            libraries.append((library_name, library_nid))
        # print(libraries)


        # Now get the function NIDs from the page
        for library_name, library_nid in libraries:
            library_section = module_soup.find('span', id=library_name)

            if not library_section:
                print('[error] Could not find library section', library_name)
                continue
            
            functions_list = []

            functions = library_section.find_all_next(['h2','h3'])
            
            for function in functions:
                # This is next library section
                if function.name == 'h2':
                    break
                
                function_name = function.text.strip()

                # Not a valid function identifier so it's probably not a function but a section
                if C_VALID_IDENTIFIER_REGEX.match(function_name) is None:
                    print('[error] Invalid function identifier:', function_name, ', skipping...')
                    continue

                # FIXME Check that function name is a valid C-function name

                function_table = function.find_next(
                    ['table', 'h2'], class_='wikitable')
                if function_table.name == 'h2':
                    print('[error] Function', function_name, 'NID table', 'cannot be found')
                    continue

                function_nid_entries = function_table.tbody.find_all("tr")
                
                for function_nid_entry in function_nid_entries:
                    bad_header = False

                    header = function_nid_entry.find_all('th')
                    if header:
                        expected_headers = ['Version', 'NID']
                        
                        if len(header) != len(expected_headers):
                            print('[error] Unexpected function NID table header size in function', function_name, ':', header)
                            bad_header = True

                        for i, expected in enumerate(expected_headers):
                            got = header[i].text.strip()
                            if got != expected:
                                print('[error] Unexpected function NID table header:', got)
                                bad_header = True

                    # Don't process this page if the header is incorrect
                    if bad_header:
                        print('[error] Skipping a function because of incorrect functions nids header:', header)
                        break

                    if header:
                        continue
                    
                    info = function_nid_entry.find_all('td')

                    # Convert to an int because floats are annoying
                    function_version = info[0].text.strip().replace('.', '')

                    # HACK: Firmware range, check if 360 is inside
                    if '-' in function_version:
                        try:
                            low, high = function_version.split('-')
                        except ValueError:
                            print('[error] function FW range incorrect:', function_version, ', skipping...')
                            break

                        if int(low) <= 360 <= int(high):
                            function_version = '360'
                        else:
                            function_version = high

                    function_version = int(function_version)
                    function_nid = info[1].text.strip()

                    functions_list.append((function_name, function_nid))
            
            print('\n==> LIBRARY', library_name)
            for n in functions_list:
                print('-', n[0], ':', n[1]) 



                    




        
    


if __name__ == "__main__":
    modules = fetch_module_urls()
    extract_nids(modules)
