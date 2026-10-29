from jwcrypto import jwe, jws, jwk
import json

priv = jwk.JWK.generate(kty='RSA', size=2048)
jwe_headers = {'alg': 'RSA-OAEP-256', 'enc': 'A128CBC-HS256', 'kid': 'k1'}
jwe_token = jwe.JWE(b'hello', jwe_headers)
jwe_token.add_recipient(priv)
print(jwe_token.serialize(compact=True))
