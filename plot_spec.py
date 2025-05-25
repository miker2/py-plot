import uuid
from typing import List, Dict, Optional, Any

class PlotSpec:
    def __init__(self,
                 name: str,
                 source_type: str,
                 unique_id: Optional[str] = None, # Allow providing one, else generate
                 file_source_identifier: Optional[str] = None,
                 original_name: Optional[str] = None,
                 expression: Optional[str] = None,
                 operation_details: Optional[Dict[str, Any]] = None,
                 input_plot_specs: Optional[List['PlotSpec']] = None):
        self.name = name
        self.source_type = source_type
        self.unique_id = unique_id if unique_id is not None else str(uuid.uuid4())
        self.file_source_identifier = file_source_identifier
        self.original_name = original_name
        self.expression = expression
        self.operation_details = operation_details
        self.input_plot_specs: List['PlotSpec'] = [] if input_plot_specs is None else input_plot_specs

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'unique_id': self.unique_id,
            'source_type': self.source_type,
            'file_source_identifier': self.file_source_identifier,
            'original_name': self.original_name,
            'expression': self.expression,
            'operation_details': self.operation_details,
            'input_plot_specs': [spec.to_dict() for spec in self.input_plot_specs] if self.input_plot_specs else []
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PlotSpec':
        return PlotSpec(
            name=data['name'],
            source_type=data['source_type'],
            unique_id=data['unique_id'],
            file_source_identifier=data.get('file_source_identifier'),
            original_name=data.get('original_name'),
            expression=data.get('expression'),
            operation_details=data.get('operation_details'),
            input_plot_specs=[PlotSpec.from_dict(spec_data) for spec_data in data.get('input_plot_specs', [])]
        )
