from enum import Enum

class MetricType(str, Enum):
    LSCC = "LSCC"
    TCC = "TCC"
    CC = "CC"
    SCOM = "SCOM"
    LCOM5 = "LCOM5"
    PAPER = "Paper Suggestion"
    CBO = "CBO"
    RFC = "RFC"
    FANIN = "FANIN"
    FANOUT = "FANOUT"
    CA = "CA"