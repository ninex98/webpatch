"""Strict JSON documents for reviewed plans and authenticated receipts."""
import json


def load_document(raw):
    def object_pairs(pairs):
        result={}
        for name,value in pairs:
            if name in result: raise ValueError('DOCUMENT_DUPLICATE_KEY')
            result[name]=value
        return result
    def constant(value): raise ValueError('DOCUMENT_NONFINITE_NUMBER')
    return json.loads(raw,object_pairs_hook=object_pairs,parse_constant=constant)
