import json, time, hashlib, base64
from jwcrypto import jwe, jws, jwk

payload_str = json.dumps({"test": 1})

# Mock keys
priv = jwk.JWK.generate(kty='RSA', size=2048)
pub = jwk.JWK.generate(kty='RSA', size=2048)

jwe_headers = {
    'alg': 'RSA-OAEP-256',
    'enc': 'A128CBC-HS256',
    'kid': 'pub-kid',
    'iat': '123456789',
    'exp': 300000,
    'issued-by': 'mid',
    'is-digested': 'true'
}

jwetoken = jwe.JWE(payload_str.encode('utf-8'), jwe_headers)
jwetoken.add_recipient(pub)
jwe_my = jwetoken.serialize(compact=True)

digest = hashlib.sha256(jwe_my.encode('utf-8')).digest()
digest_decoded = base64.b64encode(digest).decode("utf-8")

jws_headers = {
    'alg': 'RS256',
    'kid': 'priv-kid',
    'x-gl-merchantId': 'mid',
    'x-gl-enc': 'true',
    'issued-by': 'mid',
    'is-digested': 'true'
}
jws_claimset = {
    'digest': digest_decoded,
    'digestAlgorithm': 'SHA-256',
    'iat': '123456789',
    'exp': 300000,
}
jwstoken = jws.JWS(payload=json.dumps(jws_claimset, separators=(',', ':')))
jwstoken.add_signature(key=priv, protected=jws_headers)
jws_my = jwstoken.serialize(compact=True)

print("JWE My:", jwe_my.split('.')[0])
print("JWS My:", jws_my.split('.')[0])
print("JWS Payload My:", jws_my.split('.')[1])

# SDK
def json_encode(x):
    return json.dumps(x, separators=(',', ':'))

jwe_orig = jwe.JWE(payload_str.encode('utf-8'), json_encode(jwe_headers))
jwe_orig.add_recipient(pub)
jwe_orig_str = jwe_orig.serialize(compact=True)

# Note: jwe_orig_str will be different because of random IV generation in JWE!
# We can't compare the signature/payload directly if jwe_orig_str differs.
# But we can compare headers!

print("JWE Or:", jwe_orig_str.split('.')[0])

# To test JWS payload identicality, let's use the SAME jwe_my for SDK JWS!
digest2 = hashlib.sha256(jwe_my.encode()).digest()
digest_decoded2 = base64.b64encode(digest2).decode("utf-8")

jws_claimset2 = {
    'digest': digest_decoded2,
    'digestAlgorithm': 'SHA-256',
    'iat': '123456789',
    'exp': 300000,
}
jwstoken2 = jws.JWS(payload=json.dumps(jws_claimset2)) # spaces!
jwstoken2.add_signature(key=priv, protected=jws_headers)
jws_orig_str = jwstoken2.serialize(compact=True)

print("JWS Or:", jws_orig_str.split('.')[0])
print("JWS Payload Or:", jws_orig_str.split('.')[1])
