PYTHON ?= python3
XML2RFC ?= $(HOME)/.local/bin/xml2rfc

XML = draft-sobolyev-sip-digest-auth-x25519-ristretto255-schnorr-00.xml
TXT = RFC/draft-sip-digest-auth-X25519-Ristretto255-Schnorr.txt
README = README.md
README_PRE = README.md.pre

.PHONY: all clean

all: $(TXT) $(README)

$(TXT): $(XML)
	mkdir -p RFC
	$(XML2RFC) --text --out $(TXT) $(XML)

$(README): $(XML) $(README_PRE) scripts/xml2gfm.py
	$(PYTHON) scripts/xml2gfm.py $(XML) $(README) $(README_PRE)

clean:
	rm -f $(TXT) $(README)
