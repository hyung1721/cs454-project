from enum import Enum

class MetricType(str, Enum):
    LSCC = "LSCC"
    TCC = "TCC"
    SCOM = "SCOM"
    CC = "CC"
    LCOM5 = "LCOM5"
    PAPER = "Paper Suggestion"
    CBO = "CBO"
    RFC = "RFC"
    FANIN = "FANIN"
    FANOUT = "FANOUT"
    CA = "CA"