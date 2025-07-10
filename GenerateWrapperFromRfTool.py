import subprocess
import shutil
import re
from pathlib import Path
import os

# Création d'un dossier pour stocker les wrappers
WRAPPER_DIR = Path("rnaframework_wrappers")
WRAPPER_DIR.mkdir(exist_ok=True)

# Récupération de tout les outils rf-** présent dans le conda RNAframework (qu'il faut initialiser avant)
def find_rf_tools():
    rf_tools = set()
    for path_dir in os.environ["PATH"].split(os.pathsep):
        try:
            for entry in Path(path_dir).iterdir():
                if entry.name.startswith("rf-") and entry.is_file() and os.access(entry, os.X_OK):
                    rf_tools.add(entry.name)
        except Exception:
            continue
    return sorted(rf_tools)

# Récupération des aide de l'outils 'tool'
def get_help_output(tool):
    try:
        result = subprocess.run([tool, "--help"], capture_output=True, text=True)
        if result.returncode in (0, 128):
            return result.stderr # <-- sterr car c'est là que sorte les aides pour lRNAframework sinon il faut mettre stdout pour d'autres outils
        return None
    except Exception:
        return None

# Récupération du numéro de version de l'outils
def extract_version(help_text):
    match = re.search(r"\(v([\d\.]+)\)", help_text)
    return match.group(1) if match else "1.0.0"

# Récupération des données issu de l'aide
def parse_options(help_text):
    options = []
    seen = set()
    current_condition = None
    lines = help_text.splitlines()

    for line in lines:
        line = line.strip()
        # test de rajout de condition si compris dans d'autre options mais ça ne fonctionne que pour rf-map
        if "+- Bowtie v1 options" in line:
            current_condition = "bowtie2 == false"
            continue
        elif "+- Bowtie v2 options" in line:
            current_condition = "bowtie2 == true"
            continue
        elif line.startswith("|") or not line:
            continue

        # Récupération des noms des options et de leur type et stockage dans match
        match = re.match(r"((?:-\w+\s+or\s+)?--[\w\-]+)(?:\s+<([^>]+)>)?", line)

        if match:
            opt_str = match.group(1)    # <- affectation du second élément (nom long) dans opt_str
            arg_type = match.group(2)   # <- affectation du troisième élément (type) dans arg_type

            long_opt_match = re.search(r"--[\w\-]+", opt_str) # check si le nom long existe
            if not long_opt_match: # si TRUE, le nom long existe, on continue
                continue
            opt = long_opt_match.group(0) # si le nom long n'existe pas, alors on stock le nom court dans opt

            if opt in seen: # pas compris à quoi ça sert
                continue
            seen.add(opt)

            if not arg_type: # définition des types si pas de type récupéré dans l'aide, alors boolean
                opt_type = "boolean"
            elif "int" in arg_type.lower():
                opt_type = "integer"
            elif "float" in arg_type.lower():
                opt_type = "float"
            else:
                opt_type = "text"

            options.append((opt, opt_type, current_condition)) # listing des options, current condition n'est créer que dans rf-map

    return options

def create_xml(tool_name, version, options, help_text):
    xml = f'''<tool id="{tool_name}" name="{tool_name}" version="{version}">
    <command>
        <![CDATA[
        {tool_name} ${{inputs}} > ${{output}}
        ]]>
    </command>
    <inputs>
'''
    for opt, opt_type, condition in options:
        param_id = opt.lstrip("-").replace("-", "_")
        condition_str = f' condition="{condition}"' if condition else ""
        if opt_type == "boolean":
            xml += f'        <param name="{param_id}" type="boolean" truevalue="{opt}" falsevalue="" label="{opt}" optional="true"{condition_str}/>\n'
        else:
            xml += f'        <param name="{param_id}" type="{opt_type}" label="{opt}" optional="true"{condition_str}/>\n'

    xml += '''    </inputs>
    <outputs>
        <data name="output" format="txt"/>
    </outputs>
    <help><![CDATA[
'''
    xml += help_text
    xml += '''
    ]]></help>
</tool>'''
    return xml

# ==main
tools = find_rf_tools() # recherche de tout les code commancant par rf-*
for tool in tools: # pour chaque rf- dans rf-*
    print(f"[INFO] Traitement de l'outil : {tool}")
    # récupération de l'aide de l'outils
    help_output = get_help_output(tool)
    if not help_output:
        print(f"[WARNING] Aide non disponible pour {tool}")
        continue
    # Récupération de la version si disponible
    version = extract_version(help_output)
    # Récupération des options si lisible dans l'aide
    options = parse_options(help_output)
    # création du wrapper au format .xml
    xml = create_xml(tool, version, options, help_output)
    # enregistrement (écriture) du fichier xml
    (WRAPPER_DIR / f"{tool}.xml").write_text(xml)

print(f"[FINI] Tous les wrappers générés dans : {WRAPPER_DIR.resolve()}")
