import inspect
from opcode import opname


class NameNotFound(Exception):
    pass


def get_var_name(depth=2):
    frame = inspect.currentframe()
    for i in range(depth):
        frame = frame.f_back

    code = frame.f_code
    call_index = frame.f_lasti
    call_opc = opname[code.co_code[call_index]]
    if call_opc != "CALL_FUNCTION" and call_opc != "CALL_FUNCTION_KW":
        return None
    index = call_index+2
    while True:
        opc = opname[code.co_code[index]]
        if opc == "STORE_NAME" or opc == "STORE_ATTR":
            name_index = int(code.co_code[index+1])
            return code.co_names[name_index]
        elif opc == "STORE_FAST":
            name_index = int(code.co_code[index+1])
            return code.co_varnames[name_index]
        elif opc == "STORE_DEREF":
            name_index = int(code.co_code[index+1])
            return code.co_cellvars[name_index]
        elif (opc == "LOAD_GLOBAL" or opc == "LOAD_ATTR" or opc == "LOAD_FAST"
        	  or opc == "LOAD_DEREF" or opc == "DUP_TOP" or opc == "BUILD_LIST"):
            index += 2
        else:
            raise NameNotFound
