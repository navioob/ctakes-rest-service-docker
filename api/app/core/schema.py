clinical_text_refinement_schema_output = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "The comprehensive medical summary paragraph that is suitable for SNOMED-CT mapping using Apache CTAKES.",
        },
    },
    "required": ["text"],
}

tags_filtering_and_enrichment_schema_output = {
    "type": "object",
    "properties": {
        "anatomical_sites": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory anatomical_sites. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "procedures": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory procedures. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "symptoms": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory symptoms. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "diagnosis": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory diagnosis. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "medications": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory Medications. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
    },
    "required": [
        "anatomical_sites",
        "procedures",
        "symptoms",
        "diagnosis",
        "medications",
    ],
}

tags_filtering_and_enrichment_schema_output = {
    "type": "object",
    "properties": {
        "anatomical_sites": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory anatomical_sites. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "procedures": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory procedures. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "symptoms": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory symptoms. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "diagnosis": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory diagnosis. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
        "medications": {
            "type": "array",
            "description": "List of SNOMED-CT Terms and ConceptID for catergory Medications. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term for the ConceptID.",
                    },
                    "code": {
                        "type": "string",
                        "description": "ConceptID for SNOMED-CT.",
                    },
                },
                "required": ["term", "code"],
            },
        },
    },
    "required": [
        "anatomical_sites",
        "procedures",
        "symptoms",
        "diagnosis",
        "medications",
    ],
}

final_validation_schema_output = {
    "type": "object",
    "properties": {
        "anatomical_sites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "code": {"type": "string"}},
                "required": ["term", "code"],
            },
        },
        "procedures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "code": {"type": "string"}},
                "required": ["term", "code"],
            },
        },
        "symptoms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "code": {"type": "string"}},
                "required": ["term", "code"],
            },
        },
        "diagnosis": {
            "type": "object",
            "properties": {
                "communicable_disease": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}}, 
                "non_communicable_disease": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}},
            },
            "required": ["communicable_disease", "non_communicable_disease"]
        },
        "medications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "code": {"type": "string"}},
                "required": ["term", "code"],
            },
        },
    },
    "required": [
        "anatomical_sites",
        "procedures",
        "symptoms",
        "diagnosis",
        "medications",
    ],
}
