import sys
import re
import subprocess
import shutil

# Variables to substitute
PLACEHODLER_SERVICE_USER = "???SERVICEUSER???"

PLACEHOLDER_MODULE_NAME = "???MODULENAME???"

PLACEHOLDER_TABLE_NAME = "???TABLENAME???"

PLACEHODLER_WHERE_CLAUSE = "???WHERE???"

PLACEHOLDER_NEXT_ACTION = "???NEXTACTION???"

PLACEHOLDER_FIRST_ACTION_NAME = "???FIRSTACTION???"
PLACEHODLER_FIRST_ACTION_CALL = '<ok to="' + PLACEHOLDER_FIRST_ACTION_NAME + '"/>'

PLACEHODLER_LAST_ACTION_NAME = "???LASTACTION???"
LAST_ACTION_NAME = "Step_X___Table_Loads_joining"

PLACEHODLER_FORK_PLACE = "<!-- PLACEHOLDER-FORK -->"
PLACEHODLER_JOIN_PLACE = "<!-- PLACEHOLDER-JOIN -->"

FORK_ACTION_NAME = "Step_X___Table_Loads_fork"

PLACEHOLDER_LAST_ACTION_PLACE = "<!-- PLACEHOLDER-SPARK -->"
PLACEHOLDER_FIRST_ACTION_PLACE = "<!-- PLACEHOLDER -->"

PLACEHOLDER_FIRST_HIVE_QUERY_PLACE = "-- PLACEHOLDER"

workflow_template_file_path = "in/workflow.template.xml"

PLACEHODLER_DATAGEN_ACTION_NAME = "???DATAGENNAME???"
HIVE_LOAD_ACTION_NAME = "Step_8___Hive_Text_To_ORC"
DATAGEN_ACTION_NAME = "Step_8___Data_Generation"

PLACEHOLDER_MODULE = "???MODULE???"

PLACEHOLDER_TENANT = "???TENANT???"

function_call_counter = 0


def function_call_wrapper(msg, func, *args):
    global function_call_counter
    function_call_counter = function_call_counter + 1

    step_message = "Step " + str(function_call_counter) + ": "
    print(step_message + msg)

    if args.__len__() == 0:
        ret = func()
    elif args.__len__() == 1:
        ret = func(args[0])
    elif args.__len__() == 2:
        ret = func(args[0], args[1])
    elif args.__len__() == 3:
        ret = func(args[0], args[1], args[2])
    elif args.__len__() == 4:
        ret = func(args[0], args[1], args[2], args[3])
    elif args.__len__() == 5:
        ret = func(args[0], args[1], args[2], args[3], args[4])
    else:
        print("Unsupported count of incoming parameters...")
        print(step_message + "FAILURE")
        return None

    print(step_message + "SUCCESS")
    return ret


def extract_action_name(line):
    action_name_pattern = '<action name="'
    action_name_pattern_ok = '<ok to="'
    action_name_pattern_error = '<error to="'

    action_name_pattern_fork = '<fork name="'
    action_name_pattern_join = '<join name="'

    action_name_pattern_path = '<path start="'

    cred_init = '" cred="kinit"'

    if action_name_pattern in line:
        if cred_init in line:
            return line[line.find(action_name_pattern) + action_name_pattern.__len__(): line.find(cred_init)]
        else:
            return line[line.find(action_name_pattern) + action_name_pattern.__len__(): line.find('">')]
    elif action_name_pattern_ok in line:
        return line[line.find(action_name_pattern_ok) + action_name_pattern_ok.__len__(): line.find('"/>')]
    elif action_name_pattern_error in line:
        return line[line.find(action_name_pattern_error) + action_name_pattern_error.__len__(): line.find('"/>')]
    elif action_name_pattern_fork in line:
        return line[line.find(action_name_pattern_fork) + action_name_pattern_fork.__len__(): line.find('">')]
    elif action_name_pattern_join in line:
        return line[line.find(action_name_pattern_join) + action_name_pattern_join.__len__(): line.find('" to="')], \
               line[line.find(' to="') + 5: line.find('"/>')]
    elif action_name_pattern_path in line:
        return line[line.find(action_name_pattern_path) + action_name_pattern_path.__len__(): line.find('"/>')]
    else:
        return "INVALID NAME"


def explode_array(array_of_array):
    exploded = []
    for array in array_of_array:
        for cell in array:
            exploded.append(cell)
    return exploded


def split_array(array, count):
    splited = []
    fork_size = int(array.__len__() / count)

    for position in range(0, count):
        offset = position * fork_size
        if position < count - 1:
            splited.append(array[offset: offset + fork_size])
        else:
            splited.append(array[offset:])

    return splited


def build_dag(actions, properties):
    fork_count = int(properties["python.oozie.fork.count"])

    table_count = actions.__len__()

    if fork_count < 0:  # Switch-off forking
        fork_count = 1
    elif fork_count == 0:  # Automatic adjustment: 5 was tested as a good fit
        fork_count = 5

    fork_count = min(fork_count, table_count)

    forked_actions = split_array(actions, fork_count)

    for fork in forked_actions:
        for x in range(0, fork.__len__() - 1):
            next_step = extract_action_name(fork[x + 1])
            fork[x] = fork[x].replace(PLACEHOLDER_NEXT_ACTION, next_step)

    fork_code = []

    if forked_actions.__len__() <= 1:
        last_action = HIVE_LOAD_ACTION_NAME
    else:
        last_action = LAST_ACTION_NAME

    for fork in forked_actions:
        fork[fork.__len__() - 1] = fork[fork.__len__() - 1].replace(PLACEHOLDER_NEXT_ACTION, last_action)
        fork_code.append("        <path start=\"" + extract_action_name(fork[0]) + "\"/>\n")

    return explode_array(forked_actions), fork_code


def process_tables(table_list, module_name, where, properties):
    actions = []

    action_template_file = open("in/action.template.xml", "r")
    sqoop_action_template = action_template_file.read()
    action_template_file.close()

    for table_name in table_list:
        actions.append(sqoop_action_template
                       .replace(PLACEHOLDER_TABLE_NAME, table_name)
                       .replace(PLACEHOLDER_MODULE_NAME, module_name)
                       .replace(PLACEHODLER_WHERE_CLAUSE, where)
                       )

    actions, forks = build_dag(actions, properties)

    return actions, forks


def properties_sanity_check(property_kv, filename):
    key, value = property_kv.split("=", 1)
    if "{" in value or "}" in value:
        print("WARNING: Malformed property found -> key: " + key + ", value: " + value + "(" + filename + ")")
    return key, value


def parse_property_file(filename, dictionary, prefix):
    property_file = open(filename, "r")

    if prefix.__len__() > 0:
        prefix = prefix + "."

    print("INFO: Verifying properties file: " + filename)
    with property_file:
        for line in property_file:
            line = line.strip()
            if ("#" not in line) and (line.__len__() > 0):
                key, value = properties_sanity_check(line, filename)
                dictionary[prefix + key] = value.strip()

    property_file.close()

    return dictionary


def parse_properties(properties, prefix, *properties_files):
    for properties_file in properties_files:
        properties = parse_property_file(properties_file, properties, prefix)


def parse_connection(properties, connection_file_path):
    connection_file = open(connection_file_path, "r")
    text = connection_file.read()
    connection_file.close()

    # remove comments
    text = re.sub(r'#[^\n]*\n', '\n', text)

    # remove excess blank lines
    text = re.sub(r'( *\n *)+', '\n', text.strip())

    # dictionary for all connections in a file (connection -> connection information)
    databases = {}
    start = 0
    index = 0
    # Parse whole file by:
    #   1) Taking as key text on the left side of first = sign
    #   2) Taking as value text on the right side of first = sign enclosed in parenthesis
    while index < len(text):
        num_of_parenthesis = 0
        index = text.find('(')  # find first parenthesis
        while index < len(text):
            if text[index] == '(':
                num_of_parenthesis += 1
            elif text[index] == ')':
                num_of_parenthesis -= 1
            index += 1
            if num_of_parenthesis == 0:  # if == 0, we found all parenthesis for tns entry
                break

        entry = text[start:index].strip()
        pair = entry.split('=', 1)
        databases[pair[0].strip()] = pair[1].strip().replace('\n', '')
        text = text[index:]
        index = 0  # reset for next tns entry

    details = databases[properties["sqoop.oracle.global.name"]].replace(" ", "").replace(")", "").split("(")

    for param in details:
        if "HOST" in param:
            properties["python.variable.sqoop_connection_url_host"] = param.split("=")[1]
        elif "PORT" in param:
            properties["python.variable.sqoop_connection_url_port"] = param.split("=")[1]
        elif "SERVICE_NAME" in param:
            properties["python.variable.sqoop_connection_url_service_name"] = param.split("=")[1]

    return properties


def step_1_generate_actions(module_name, table_list, scn, properties):
    scn_query = ""

    if scn:
        scn_query = " AS OF SCN ${wf:actionData('Step_5___Get_SCN_NUMBER')['scn']}"

    where = scn_query + " t WHERE $CONDITIONS"

    action_list, forks = process_tables(table_list, module_name, where, properties)

    return action_list, forks


def step_2_generate_workflow(action_list, module_name, forks):
    workflow_template_file = open(workflow_template_file_path, "r")
    workflow_file = open("../oozie/workflow/workflow.xml", "w+")

    for line in workflow_template_file.readlines():
        if PLACEHODLER_FIRST_ACTION_CALL in line:
            if forks.__len__() > 1:
                workflow_file.write(line.replace(PLACEHOLDER_FIRST_ACTION_NAME, FORK_ACTION_NAME))
            else:
                workflow_file.write(line.replace(PLACEHOLDER_FIRST_ACTION_NAME, extract_action_name(action_list[0])))
        elif PLACEHODLER_LAST_ACTION_NAME in line:
            workflow_file.write(line.replace(PLACEHODLER_LAST_ACTION_NAME, LAST_ACTION_NAME))
        elif PLACEHOLDER_MODULE_NAME in line:
            workflow_file.write(line.replace(PLACEHOLDER_MODULE_NAME, module_name))
        elif PLACEHODLER_FORK_PLACE in line:
            if forks.__len__() > 1:
                workflow_file.write("    <fork name=\"" + FORK_ACTION_NAME + "\">\n")
                for fork in forks:
                    workflow_file.write(fork)
                workflow_file.write("    </fork>\n")
        elif PLACEHODLER_JOIN_PLACE in line:
            if forks.__len__() > 1:
                workflow_file.write(
                    "    <join name=\"" + LAST_ACTION_NAME + "\" to=\"" + HIVE_LOAD_ACTION_NAME + "\"/>\n")
        elif PLACEHOLDER_FIRST_ACTION_PLACE not in line:
            workflow_file.write(line)
        else:
            for action_line in action_list:
                if '<ok to="End"/>' not in action_line:
                    workflow_file.write(action_line)
                else:
                    workflow_file.write(action_line.replace("End", LAST_ACTION_NAME))

    workflow_template_file.close()
    workflow_file.close()

    return 0


def step_3_generate_properties(module_name, properties):
    job_properties_template_file = open("in/job.template.properties", "r")
    job_properties_file = open("../oozie/job.properties", "w+")

    for line in job_properties_template_file:
        line = line \
            .replace(PLACEHOLDER_MODULE_NAME, module_name) \
            .replace(PLACEHOLDER_MODULE, module_name.lower()) \
            .replace(PLACEHOLDER_TENANT, properties["python.variable.tenant"])

        if "#" not in line:
            key_value = line.strip().split("=")
            if key_value.__len__() > 1:
                old = key_value[1]
                new = properties.get(old, "")
                if new.__len__() > 0:
                    job_properties_file.write(line.replace(old, new))
                else:
                    job_properties_file.write(line)
        else:
            job_properties_file.write(line)

    job_properties_template_file.close()
    job_properties_file.close()

    return 0


def step_4_generate_hive_script(table_list):
    hive_template_file = open("in/prepare-hive.template.hql", "r")
    hive_file = open("../oozie/workflow/scripts/prepare-hive.hql", "w+")

    for line in hive_template_file:
        if PLACEHOLDER_FIRST_HIVE_QUERY_PLACE not in line:
            hive_file.write(line)
        else:
            for table in table_list:
                hive_file.write("DROP TABLE IF EXISTS `${database_data}`.`" + table + "`;\n")

    hive_template_file.close()
    hive_file.close()


def step_copy_generatehivetablescripts(table_list):
    hive_template_file = open("in/generate_create_table_statment.hql", "r")
    hive_file = open("../oozie/workflow/scripts/generate_create_table_statment.hql", "w+")

    for line in hive_template_file:
        if PLACEHOLDER_FIRST_HIVE_QUERY_PLACE not in line:
            hive_file.write(line)
        else:
            for table in table_list:
                hive_file.write("DROP TABLE IF EXISTS `${database_data}`.`" + table + "`;\n")

    hive_template_file.close()
    hive_file.close()


def step_generate_create_tables_script(properties, table_list):
    hive_file = open("in/create-hive-tables.template.sh", "r")
    hive_file_write = open("../oozie/workflow/scripts/create-hive-tables.sh", "w+")
    step_copy_generatehivetablescripts(table_list)
    hive_file_write.write("#!/bin/bash" + "\n")
    for line in hive_file:
        if "#" not in line:
            hive_file_write.write(line)
    hive_file.close()
    hive_file_write.close()


def step_importmetadata(properties):
    job_properties_template_file = open("in/metadata_import.sh", "r")
    job_properties_file = open("../oozie/workflow/scripts/metadata_import.sh", "w+")

    for line in job_properties_template_file:
        if "#" not in line:
            key_value = line.strip().split("=")
            if key_value.__len__() > 1:
                old = key_value[1]
                new = properties.get(old, "")
                if new.__len__() > 0:
                    job_properties_file.write(line.replace(old, new))
                else:
                    job_properties_file.write(line)
        else:
            job_properties_file.write(line)

    job_properties_template_file.close()
    job_properties_file.close()


def step_preparehivedatabases(properties):
    job_properties_template_file = open("in/prepare-hive.template.sh", "r")
    job_properties_file = open("../oozie/workflow/scripts/prepare-hive.sh", "w+")

    for line in job_properties_template_file:
        if "#" not in line:
            key_value = line.strip().split("=")
            if key_value.__len__() > 1:
                old = key_value[1]
                new = properties.get(old, "")
                if new.__len__() > 0:
                    job_properties_file.write(line.replace(old, new))
                else:
                    job_properties_file.write(line)
        else:
            job_properties_file.write(line)

    job_properties_template_file.close()
    job_properties_file.close()


def step_5_generate_run_script(properties):
    run_script_file = open("../oozie/run-oozie.sh", "w+")

    hdfs_oozie_path = "/user/" + properties["python.variable.service_user"] + "/oozie-initial-load-" + properties[
        "python.variable.module_name"] + "/"

    run_script_file.write("#!/bin/bash\n")
    # run_script_file.write("./workflow/scripts/kafka-cleanup.sh"+ "\n")
    # run_script_file.write("if [ $? -eq 0 ]"+ "\n")
    # run_script_file.write("then"+ "\n")
    run_script_file.write("hdfs dfs -rm -r -f " + hdfs_oozie_path + "\n")
    run_script_file.write("hdfs dfs -mkdir -p " + hdfs_oozie_path + "\n")
    run_script_file.write("hdfs dfs -put -f * " + hdfs_oozie_path + "\n")
    #run_script_file.write("sh workflow/scripts/prepare-hive.sh" + "\n")
    #run_script_file.write("sh workflow/scripts/metadata_import.sh" + "\n")
    #run_script_file.write("sh workflow/scripts/create-hive-tables.sh" + "\n")
    #run_script_file.write("hive -f create_hive_tables.txt" + "\n")
    #run_script_file.write("rm -rf create_hive_tables.txt" + "\n")
    run_script_file.write("output=`./oozie.sh -config job.properties -run`\n")
    run_script_file.write("echo ${output}" + "\n")
    run_script_file.write("jobid=$(echo ${output} | tail -1 | sed \"s/job: //\")\n")

    run_script_file.write("echo \"Use following command to:\"\n")
    run_script_file.write("echo \"\tSee job info     :\n")
    run_script_file.write("./oozie.sh -info ${jobid}\"\n")
    run_script_file.write("echo \"\tWatch job info   :\n")
    run_script_file.write('watch -n 5 "./oozie.sh -info ${jobid} | tail -n50""\n')
    run_script_file.write("echo \"\tKill the job     :\n")
    run_script_file.write("./oozie.sh -kill ${jobid}\"\n")

    run_script_file.write('echo "Advanced job commands to:"\n')
    run_script_file.write('echo "\tRe-run failed nodes - only for table reload:\n')
    run_script_file.write('./oozie.sh -rerun ${jobid} -Doozie.wf.rerun.failnodes=true"\n')

    run_script_file.write('echo "\tRe-run datagen only:\n')
    run_script_file.write('./rerun-datagen.sh ${jobid}"\n')
    # run_script_file.write("fi"+ "\n")

    run_script_file.close()


def step_6_generate_oozie_script(properties):
    oozie_script_file = open("../oozie/oozie.sh", "w+")

    oozie_script_file.write("#!/bin/bash\n\n")
    oozie_script_file.write("# Example:\n")
    oozie_script_file.write("# ./oozie.sh -info <oozie_job_id>      - job progress status\n")
    oozie_script_file.write("# One can combine with watch command to update automatically\n")
    oozie_script_file.write("# watch -n 5 \"./oozie.sh -info <oozie_job_id> |tail -n50\" \n\n")
    oozie_script_file.write("# watch -n 5 \"./oozie.sh -info <oozie_job_id> | tail -n50\"\n\n")
    oozie_script_file.write("oozie job -oozie " + properties["oozie.address"] + " $@\n")
    oozie_script_file.write("\n")

    oozie_script_file.close()


def step_generate_hive_final_table_script(table_list):
    hive_template_file = open("in/hive-text-to-orc-template.hql", "r")
    hive_file = open("../oozie/workflow/scripts/hive-text-to-orc.hql", "w+")

    for line in hive_template_file:
        if PLACEHOLDER_FIRST_HIVE_QUERY_PLACE not in line:
            hive_file.write(line)
        else:
            for table in table_list:
                hive_file.write(
                    "CREATE TABLE `${database_data}`.`" + table + "` AS SELECT * FROM `${database_tmp_data}`.`" + table + "`;\n")

    hive_template_file.close()
    hive_file.close()


def step_generate_hive_countMatch_table_script(table_list):
    hive_template_file = open("in/hive-insert-count-template.hql", "r")
    hive_file = open("../oozie/workflow/scripts/hive-insert-count.hql", "w+")

    for line in hive_template_file:
        if PLACEHOLDER_FIRST_HIVE_QUERY_PLACE not in line:
            hive_file.write(line)
        else:
            for table in table_list:
                hive_file.write(
                    "INSERT INTO TABLE  `${database_summary}`.`${table_summary_tmp}` (SELECT COUNT(*) , '" + table + "' FROM `${database_data}`.`" + table + "`);\n")

    hive_template_file.close()
    hive_file.close()


def get_all_nodes():
    workflow_file = open("../oozie/workflow/workflow.xml", "r")

    nodes = {}
    src = ''

    for line in workflow_file:
        if ("action name=" in line) or ("fork name=" in line):
            src = extract_action_name(line)
            if src not in nodes:
                nodes[src] = {}
                nodes[src]['ok'] = []
                nodes[src]['err'] = []
                nodes[src]['in'] = []
        elif "join name" in line:
            src, dst = extract_action_name(line)
            nodes[src] = {}
            nodes[src]['ok'] = []
            nodes[src]['err'] = []
            nodes[src]['ok'].append(dst)

            nodes[dst] = {}
            nodes[dst]['ok'] = []
            nodes[dst]['err'] = []
            nodes[dst]['in'] = []

            nodes[dst]['in'].append(src)
        elif "ok to=" in line:
            nodes[src]['ok'].append(extract_action_name(line))
            nodes[src]['in'].append(extract_action_name(line))
        elif "error to" in line:
            nodes[src]['err'].append(extract_action_name(line))
            nodes[src]['in'].append(extract_action_name(line))
        elif "path start" in line:
            nodes[src]['ok'].append(extract_action_name(line))

    return nodes


def generate_documentation(nodes):
    graph_file = open("../oozie/graph.dot", "w+")
    graph_file.write("digraph graphname {\n")

    for node in nodes:
        for dst in nodes[node]['ok']:
            graph_file.write("    " + node + " -> " + dst + " [color=green];\n")
        for dst in nodes[node]['err']:
            graph_file.write("    " + node + " -> " + dst + " [color=red];\n")

    graph_file.write("}\n")
    graph_file.close()

    subprocess.call(["dot", "-Tpdf", "../oozie/graph.dot", "-o", "../oozie/graph.pdf"])


def generate_datagen(nodes):
    datagen = open("../oozie/rerun-datagen.sh", "w+")

    datagen.write('#!/bin/bash\n')

    exclude = ''

    for node in nodes:
        if DATAGEN_ACTION_NAME not in node:
            exclude = exclude + node + ","

    # Remove excessive comma
    exclude = exclude[:exclude.__len__() - 1]

    datagen.write('./oozie.sh -rerun $1 -Doozie.wf.rerun.skip.nodes=' + exclude + "\n")

    datagen.close()


def main(args):
    print("Welcome to Oozie Workflow generation script!")

    module_name = args[0]
    user_name = args[1]
    tns_admin_file = args[2]
    tenant = args[3]

    if args.__len__() > 4 and args[4] == "DEBUG":
        general_property_file_path = "../../../conf/templates/general.properties.template"
        general_source_system_properties_file_path = "../../../conf/templates/initialload-oracle-pipeline.properties" \
                                                     ".template "
        source_system_properties_file_path = "../../../conf/templates/initialload-oracle-pipeline_" + module_name + \
                                             ".properties.template"
    else:
        general_property_file_path = "../conf/general.properties"
        general_source_system_properties_file_path = "../conf/initialload-oracle-pipeline.properties"
        source_system_properties_file_path = "../conf/initialload-oracle-pipeline_" + module_name + ".properties"

    properties = {}
    parse_properties(properties, "", general_property_file_path, general_source_system_properties_file_path,
                     source_system_properties_file_path)
    parse_properties(properties, "oozie-datagen", general_property_file_path,
                     general_source_system_properties_file_path, source_system_properties_file_path)

    properties["python.variable.service_user"] = user_name
    properties["python.variable.module_name"] = module_name
    properties["python.variable.tenant"] = tenant

    properties = parse_connection(properties, tns_admin_file)

    scn = properties["sqoop.scn.enabled"]

    table_list = properties["oracle.schema.tables"].split(" ")

    properties["oracle.schema.tables"] = properties["oracle.schema.tables"].replace(" ",",")
    properties["oozie.hive2.jdbc.url"] = properties["oozie.hive2.jdbc.url"].replace("'","")

    action_list, forks = function_call_wrapper("Generating Sqoop Actions", step_1_generate_actions, module_name,
                                               table_list,
                                               "true" in scn, properties)

    function_call_wrapper("Generating Workflow", step_2_generate_workflow, action_list, module_name,
                          forks)

    function_call_wrapper("Generating Properties for Workflow", step_3_generate_properties, module_name, properties)

    function_call_wrapper("Generating Hive Script", step_4_generate_hive_script, table_list)

    function_call_wrapper("Generating Hive Final Data Load Script", step_generate_hive_final_table_script, table_list)

    function_call_wrapper("Generating Hive Final Count Script", step_generate_hive_countMatch_table_script, table_list)

    function_call_wrapper("Generating Oozie Run Script", step_5_generate_run_script, properties)

    function_call_wrapper("Generating Oozie Script", step_6_generate_oozie_script, properties)

    function_call_wrapper("Generating Hive Script for table creation", step_generate_create_tables_script, properties,
                          table_list)
    """
    function_call_wrapper("Generating Shell Script for Sqoop import metadata table", step_importmetadata, properties)

    function_call_wrapper("Generating Shell Script for Prepareing hive tables", step_preparehivedatabases, properties)
    nodes = get_all_nodes()

    if args.__len__() > 4 and args[4] == "DEBUG":
        function_call_wrapper("Generating Visualization Graph", generate_documentation, nodes)

    function_call_wrapper("Generating Data Generation command", generate_datagen, nodes)
    """
    print("Generation script completed: SUCCESS")
    for key, value in properties.items():
        print(key +" : "+ value)


if __name__ == '__main__':
    args = ["ICE", "e032_s_dp-de-e-dp", "../conf/tnsnames.ora", "DEVP_DE"]
    main(args)

