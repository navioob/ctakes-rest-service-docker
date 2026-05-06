# JSON Schemas for LLM Structured Output (Response Format)
# These schemas ensure the LLM returns data in a consistent format that the application can parse.

# Schema for Step 1: Clinical Text Refinement
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

# Schema for Step 3: Tags Filtering and Enrichment
tags_filtering_and_enrichment_schema_output = {
    "type": "object",
    "properties": {
        "anatomical_sites": {
            "type": "array",
            "description": "List of SNOMED-CT Terms for category anatomical_sites. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term.",
                    },
                },
                "required": ["term"],
            },
        },
        "procedures": {
            "type": "array",
            "description": "List of SNOMED-CT Terms for category procedures. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term.",
                    },
                },
                "required": ["term"],
            },
        },
        "symptoms": {
            "type": "array",
            "description": "List of SNOMED-CT Terms for category symptoms. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term.",
                    },
                },
                "required": ["term"],
            },
        },
        "diagnosis": {
            "type": "array",
            "description": "List of SNOMED-CT Terms for category diagnosis. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term.",
                    },
                },
                "required": ["term"],
            },
        },
        "medications": {
            "type": "array",
            "description": "List of SNOMED-CT Terms for category Medications. Can be an empty list [].",
            "items": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Description of SNOMED-CT Term.",
                    },
                },
                "required": ["term"],
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

# Schema for Step 4: Final Validation and Diagnosis Categorization
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
