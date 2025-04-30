from typing import Any, Dict, List, Tuple
from fastapi.openapi.utils import get_openapi_security_definitions
from fastapi.dependencies.models import Dependant

# Lưu lại hàm gốc để tham khảo
original_get_openapi_security_definitions = get_openapi_security_definitions

# Định nghĩa hàm thay thế
def patched_get_openapi_security_definitions(
    flat_dependant: Dependant
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    security_definitions = {}
    operation_security = []
    
    for security_requirement in flat_dependant.security_requirements:
        # Kiểm tra xem security_scheme có thuộc tính model không
        if not hasattr(security_requirement.security_scheme, 'model'):
            # Tạo security_definition mặc định cho OAuth2
            security_definition = {
                "type": "oauth2",
                "flows": {
                    "password": {
                        "tokenUrl": getattr(security_requirement.security_scheme, 'tokenUrl', '/token'),
                        "scopes": {}
                    }
                }
            }
        else:
            # Nếu có thuộc tính model, sử dụng cách xử lý ban đầu
            from fastapi.encoders import jsonable_encoder
            security_definition = jsonable_encoder(
                security_requirement.security_scheme.model,
                by_alias=True,
                exclude_none=True,
            )
        
        # Lấy tên scheme
        security_name = security_requirement.security_scheme.scheme_name
        security_definitions[security_name] = security_definition
        operation_security.append({security_name: security_requirement.scopes})
    
    return security_definitions, operation_security

# Thực hiện monkey patching
import fastapi.openapi.utils
fastapi.openapi.utils.get_openapi_security_definitions = patched_get_openapi_security_definitions

# In thông báo xác nhận
print("✅ FastAPI OpenAPI security definitions patched successfully")