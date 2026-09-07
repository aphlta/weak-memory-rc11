# S6a 机械化（Coq）

COQPROJECT := _CoqProject
COQFLAGS  := -R . Formal
VFILES    := MiniGraph.v Reduction.v IndProp.v
VOFILES   := $(VFILES:.v=.vo)

COQDOCKER ?= coqorg/coq:8.18.0

.PHONY: all clean docker

all: $(VOFILES)

MiniGraph.vo: MiniGraph.v
	coqc $(COQFLAGS) MiniGraph.v

Reduction.vo: Reduction.v MiniGraph.vo
	coqc $(COQFLAGS) Reduction.v

IndProp.vo: IndProp.v Reduction.vo MiniGraph.vo
	coqc $(COQFLAGS) IndProp.v

docker:
	docker run --rm \
	  -v "$(CURDIR)":/home/coq/formal -w /home/coq/formal \
	  $(COQDOCKER) make all

clean:
	rm -f *.vo *.glob *.vos *.vok .*.aux
