PYTHON ?= python3
XML2RFC ?= $(HOME)/.local/bin/xml2rfc

XML = draft-sobolyev-sip-digest-auth-x25519-ristretto255-schnorr-00.xml
TXT = RFC/draft-sip-digest-auth-X25519-Ristretto255-Schnorr.txt
README = README.md

.PHONY: all clean

all: $(TXT) $(README)

$(TXT): $(XML)
	mkdir -p RFC
	$(XML2RFC) --text --out $(TXT) $(XML)

$(README): $(XML) scripts/xml2gfm.py
	$(PYTHON) scripts/xml2gfm.py $(XML) $(README)

clean:
	rm -f $(TXT) $(README)
