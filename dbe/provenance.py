"""Provenance, disclosure and consent (WP-26).

**Content credentials (C2PA).** A finished film is signed with a C2PA manifest (c2pa-python, the Content Authenticity
Initiative's library) that says what it is and how it was made: created by Doodleberry with a composite of drawn
characters, algorithmic animation and trained models (IPTC digital source type `compositeWithTrainedAlgorithmicMedia`
when a synthetic voice or another model shaped it), its title and channel, the voices and models that made it with
their licence status and consent basis, the AI-disclosure text, a do-not-train request (`c2pa.training-mining`), and
its **recipe** (E14): the hashes of the film's data (shots, script, timing, data, facts), the engine files and the
frame keys of every frame, so anyone with the repository can re-make a frame and check it matches what was signed.

The signer is the studio's own certificate chain, made on first use and kept with the production registry (never in
git): a root CA and an ES256 signing certificate it issues (C2PA does not accept self-signed signers; the signing
certificate carries digitalSignature and the document-signing and email-protection usages). Anyone given the root
certificate (`trust_anchors.pem`, written beside each signed film) can verify the film with c2patool, the reference
tool; a viewer without it sees a valid signature from an untrusted issuer. A certificate from a CA on the C2PA trust
list can replace the studio's (put its chain and key in the registry's keys folder).

**Disclosure.** Each platform's AI-disclosure setting and caption line (dbe/disclosure.json), decided from what made
the film: synthetic voices, models that drew or changed the picture, realistic people or not.

**Consent.** consent/records.json holds consent records (who, for what: a voice or a likeness, which uses, from when,
until when, revoked or not, and the hash of the signed form kept off git). Every voice a film uses needs a consent
basis: stock synthetic voices carry their licence as the basis (voices/registry.json); a voice made from a person
(a clone, a recording) needs a live consent record covering the use, else voice.build refuses it. A puppet that
depicts a real person (meta.likeness) needs the same for its likeness.
"""
import datetime as dt
import hashlib
import os
import json
import subprocess
from pathlib import Path

from . import ROOT

C2PATOOL = next((p for p in [Path(d) / "c2patool" / "c2patool" for d in (os.environ.get("DBE_OPT"), "/opt", str(Path.home() / ".local" / "opt")) if d]
                 if p.exists()), Path("/opt/c2patool/c2patool"))   # /opt, or ~/.local/opt without root (tools/setup.sh)
IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"
EKU_DOC_SIGNING = "1.3.6.1.5.5.7.3.36"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------------- the studio's certificates ----------------
def ensure_keys(keydir):
    """a root CA and an ES256 signing certificate it issues (made once, kept in keydir) -> paths"""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier
    keydir = Path(keydir); keydir.mkdir(parents=True, exist_ok=True)
    paths = {"root": keydir / "root-ca.pem", "chain": keydir / "signer-chain.pem", "key": keydir / "signer-key.pem"}
    if all(p.exists() for p in paths.values()):
        return paths
    now = dt.datetime.now(dt.timezone.utc)
    rk = ec.generate_private_key(ec.SECP256R1()); sk = ec.generate_private_key(ec.SECP256R1())
    rname = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Doodleberry studio"), x509.NameAttribute(NameOID.COMMON_NAME, "Doodleberry studio root CA")])
    root = (x509.CertificateBuilder().subject_name(rname).issuer_name(rname).public_key(rk.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(rk.public_key()), critical=False)
            .sign(rk, hashes.SHA256()))
    sname = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Doodleberry studio"), x509.NameAttribute(NameOID.COMMON_NAME, "Doodleberry film signer")])
    signer = (x509.CertificateBuilder().subject_name(sname).issuer_name(rname).public_key(sk.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=1095))
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False,
                                           key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
              .add_extension(x509.ExtendedKeyUsage([ObjectIdentifier(EKU_DOC_SIGNING), ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(sk.public_key()), critical=False)
              .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(rk.public_key()), critical=False)
              .sign(rk, hashes.SHA256()))
    pem = lambda c: c.public_bytes(serialization.Encoding.PEM)
    paths["root"].write_bytes(pem(root)); paths["chain"].write_bytes(pem(signer) + pem(root))
    paths["key"].write_bytes(sk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    paths["key"].chmod(0o600)
    return paths


# ---------------- the manifest ----------------
def manifest(title, channel, made_with, disclosure, recipe, ai_shaped, version="1"):
    """a C2PA manifest definition (JSON) for one film"""
    src = IPTC + ("compositeWithTrainedAlgorithmicMedia" if ai_shaped else "digitalCreation")
    return {
        "claim_generator_info": [{"name": "Doodleberry", "version": version}],
        "title": title,
        "assertions": [
            {"label": "c2pa.actions.v2", "data": {"actions": [
                {"action": "c2pa.created", "digitalSourceType": src, "softwareAgent": {"name": "Doodleberry", "version": version},
                 "description": "drawn characters animated from data; voices and other model outputs listed in org.doodleberry.provenance"}]}},
            {"label": "stds.schema-org.CreativeWork", "data": {"@context": "https://schema.org", "@type": "CreativeWork", "name": title,
                                                              "author": [{"@type": "Organization", "name": channel}]}},
            {"label": "c2pa.training-mining", "data": {"entries": {
                "c2pa.ai_generative_training": {"use": "notAllowed"}, "c2pa.ai_inference": {"use": "notAllowed"},
                "c2pa.ai_training": {"use": "notAllowed"}, "c2pa.data_mining": {"use": "notAllowed"}}}},
            {"label": "org.doodleberry.provenance", "data": {"made_with": made_with, "disclosure": disclosure}},
            {"label": "org.doodleberry.recipe", "data": recipe},
        ],
    }


def sign(src, dst, man, keys, ta_url=None):
    import c2pa
    info = c2pa.C2paSignerInfo(alg=b"es256", sign_cert=Path(keys["chain"]).read_bytes(), private_key=Path(keys["key"]).read_bytes(),
                               ta_url=ta_url.encode() if ta_url else None)
    signer = c2pa.Signer.from_info(info)
    b = c2pa.Builder(json.dumps(man))
    with open(src, "rb") as s, open(dst, "w+b") as d:
        b.sign(signer, "video/mp4", s, d)
    return dst


def read(path):
    """the manifest store as c2pa-python reads it, and its validation state"""
    import c2pa
    with c2pa.Reader(str(path)) as r:
        return json.loads(r.json()), r.get_validation_state()


def verify(path, trust_pem=None, tool=C2PATOOL):
    """c2patool's reading (the reference implementation), with the studio root as a trust anchor when given ->
    {state, errors, assertions}"""
    cmd = [str(tool), str(path)]
    if trust_pem:
        cmd += ["trust", "--trust_anchors", str(trust_pem)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
    except Exception:
        return {"state": "unreadable", "errors": [(r.stderr or r.stdout)[-300:]]}
    act = j.get("manifests", {}).get(j.get("active_manifest"), {})
    vr = j.get("validation_results") or {}
    am = vr.get("activeManifest") or {}
    failures = [x.get("code") for x in am.get("failure", [])] + [x.get("code") for x in (j.get("validation_status") or []) if x.get("code") and "fail" in x.get("code", "") + x.get("explanation", "")]
    return {"state": j.get("validation_state") or ("Invalid" if failures else "Valid"), "failures": sorted(set(f for f in failures if f)),
            "success": sorted({x.get("code") for x in am.get("success", [])}), "assertions": [a.get("label") for a in act.get("assertions", [])],
            "issuer": (act.get("signature_info") or {}).get("issuer"), "title": act.get("title")}


# ---------------- disclosure ----------------
def disclosure(rules, voices, models, realistic=False):
    """each platform's AI-disclosure setting and caption line, from what made the film"""
    synthetic_voice = any(v.get("synthetic", True) for v in voices)
    ai_picture = any(m.get("touches") == "picture" for m in models)
    reasons = (["synthetic voices (text-to-speech)"] if synthetic_voice else []) + (["model-made picture elements"] if ai_picture else [])
    out = {}
    for plat, r in rules["platforms"].items():
        need = r["required_when"]
        on = (realistic and bool(reasons)) if need == "realistic" else (bool(realistic and reasons) or synthetic_voice) if need == "realistic_audio" \
            else bool(reasons) if need == "any_ai" else False
        out[plat] = {"setting": r["setting"], "on": on or (bool(reasons) and r.get("we_disclose_anyway", False)), "required": on,
                     "caption": rules["caption"].format(what=" and ".join(reasons)) if reasons else rules["caption_none"],
                     "note": r["note"], "source": r["source"], "checked": r.get("checked")}
    return {"reasons": reasons, "platforms": out}


# ---------------- consent ----------------
def consent_store(root=ROOT):
    f = Path(root) / "consent" / "records.json"
    return json.loads(f.read_text()) if f.exists() else {"note": "WP-26: consent records (dbe/provenance.py)", "records": []}


def live(rec, use, today=None):
    """a record in force for a use (a dict: kind, film, platform, commercial)"""
    today = today or dt.date.today().isoformat()
    if rec.get("revoked"):
        return False, f"revoked on {rec['revoked']}"
    if rec.get("granted_on", "9999") > today:
        return False, "not yet in force"
    if rec.get("expires") and rec["expires"] < today:
        return False, f"expired on {rec['expires']}"
    sc = rec.get("scope") or {}
    if use.get("kind") and rec.get("kind") != use["kind"]:
        return False, f"a {rec.get('kind')} consent, not {use['kind']}"
    if use.get("commercial") and not sc.get("commercial", False):
        return False, "does not cover commercial use"
    if sc.get("platforms") and use.get("platform") and use["platform"] not in sc["platforms"]:
        return False, f"does not cover {use['platform']}"
    return True, "in force"


def voice_basis(vid, reg, store, use=None, today=None):
    """(ok, why): a stock synthetic voice stands on its licence; a voice from a person needs a live consent record"""
    r = reg.get(vid)
    if r is None:
        return False, "not in voices/registry.json"
    if r.get("kind") in ("clone", "person", "recording") or r.get("person"):
        cid = r.get("consent")
        rec = next((x for x in store["records"] if x["id"] == cid), None) if cid else None
        if not rec:
            return False, f"{vid} is made from a person's voice and has no consent record"
        ok, why = live(rec, {**(use or {}), "kind": "voice"}, today)
        return ok, f"consent {cid}: {why}"
    if not r.get("license") and not r.get("status"):
        return False, "no licence recorded: no consent basis"
    return True, f"stock synthetic voice: licence basis ({r.get('status', '?')})"
