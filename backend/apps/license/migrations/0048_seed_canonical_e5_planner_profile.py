"""Install the audited E5 profile without replacing tenant configuration.

The document is version-controlled in ``sion_planner_config.e1_e5``; this
migration deliberately uses only historical ORM models for persistence.
Existing divergent rows abort the migration with an actionable diagnostic.
"""
import base64
import json
import zlib
from decimal import Decimal

from django.db import migrations


# Frozen, canonical E5 profile JSON (zlib + base85).  This migration must not
# import mutable application configuration when it is replayed in the future.
_E5_DOCUMENT_B85 = "c$~FZTW_065dJF`&sGn1?4BOph*>AAV4#4TMn}~O<F&I2w}T;RROP>)nFU`kwv#w*9-@?;o%!bW&1`=uL0E`1St;7Tzv{nP@tko*Qzp7Ux>mYMm?jIcRJ318oX+uJOkK}s>*KtPcy&Dt3cgJ9XAm(c@pbpEGp3g=0U`b~%lT>r+EEW^oQtj5h2YT~E>WLM*bTV@`84BsP^3A09od$zQ_F*|k3m!-fVtpBkUw`8VwQ8|rMp$(xVAAJ`OF~R$fb@?ZR@?-el+B5S9w7LJHFjs6W#BOO?&FLJbSk*Pxm}1I*TYR^Om6rHE%k#N8V9W*Pg`;dPSwkX=Ca@9ki^FtE-M~UQQ>}>ipHYbw<C#(#25iw=B720%Fv<>e$pg?$DcKmqy}|cTy3xEIGP4>D&<4A|~2;YXQE)!QQZU@!`sQ<Vz^MSyVgGJtGF$L;8l2buWz$#>6%Wwf;;rdgtNKXY;q<KV3QRbie~@@;!D-{p*GgAI>MAi%l|r3yr)d1wFN=!VlQ_@zPbYT%@@uz)-KNtYnd~2QK@4sOckgM^n|FHZpb3qvJd2dz1gKTzl#?_<#1i9t&)w`{c@YF~JC&=Z~C;Br6M+=5r1hi@f9w9Q_kG`dVeI4MI0f8*Mdk1kn<e-p3dU-EoM)#`HV<c0rQe!Y_9W7vWA&7AfFbm5YT41y2e#3!)$iQS}WWPIUv4V7u(=RJVNUqe~|y8K78|F=siC1CfYiS-IL(mU)nrQBXN68vutRC_*~?1c`xv@hr^?xN{7WOQ7aR1xmsjPfc?RtP#(P<MHgNS_Su<c-odhQH^f0OINqnD?rs?2f8g-E_1%D{Pd=i17Q?$KWL4!_TXvu%#{y9D;SJ2G*fF#O-L*;b_ZIcWj8FrMs%#Sbv18Ad{LafWa6b<Ebj{$q<jf^Pl`X`^&u}MT|khFAVHkHPs1Hjk*QE7Q`4u8d51mUK(1SOAD4@SErMvp(Sb~4JQ4|-K^A5HHL;jwyA#MXqTJlTdX^ra*F3R^9@rT{koW3_L2tXeh&_jlXbrSNUQdFL_7nvFL1b*lR3jvfmKz*zxxT8cA%4?MYUpxcoY8-_Yhd~}1iQm*ALcXBUew#0(k266sy;cfMr=g;ZPERSUCR!U39(ua(&ah}Eavfy=c{{>Vfh?Q{^2_Q@tc`;cs%VFswSbd6YV)B^<T}h^a$7T$_wZOCRgXKG7DA$vZY+=CXg^ec47``WOY`C54`51uzH$#w>Yum;3ot4VckipY|3QwNnKB)1<yHzqbXbQj?`wfw0&-Cs|~cZNm)$wi6_ncDPyR=u8z;L?d3<XP=6eJ8lZu8!7z_}of3$KZtl^}AyY?c>u3qB07Zk1p0bd=@@_(rb7=_g?u4R0Y!>0?<3%`7wI+?fn{>8Aa9wWRweG%+cA8|vHZ0U!qng|9Yq`W2utl23Ak?0{hv&U?`_-wuk7a+P8uS}AaB+H_LSCbdzmI2ZsA>`fo7fIJxc9<3Y#EJwNw4KJEfZ1HT?Y05PQvFb6br0cSjIz9JtGF_L%pQ3a>ZAyO!Bl$<{&-iGl9{pR#*8|uCnrFLB8X&XRO0^(e&ucagY8{wF<Iq_-&D4;Xp5oxQy9<C9E=4$|YrlQ2;L<2&@b~JNUm#)w-QYfi)#oi`wo<eRW$yjYmM^T>?Tb3Ru(0CD5tvVc*7S!k<}M7AUwM!Z3~D^UlW4f<?h|#)I&liGs(QFm5X5fXC?YDg(_y#9$E>^UCQuFAEWYN=VH1M*V<_gDeA;Rpr+RtLRtk+<fS*_sHsOKUouaD?z(xc#0+0Q0MKb>+h)ZPO9?`sjCRF`CM76tIm$8!&9sxOaZGW5g8u10OStaGLa|97|Z7k;mN9G4t0o0EtGf!#+NDWz5EZVlB`k"


def seed_e5(apps, schema_editor):
    Sion = apps.get_model("core", "SionNormClassModel")
    Profile = apps.get_model("license", "SionPlanningProfile")
    Action = apps.get_model("license", "SionPlanningAction")
    Mapping = apps.get_model("license", "SionPlanningOutputMapping")
    Rule = apps.get_model("license", "SionPlanningRule")
    document = json.loads(zlib.decompress(base64.b85decode(_E5_DOCUMENT_B85)).decode())
    sions = list(Sion.objects.filter(norm_class__iexact="E5").order_by("pk"))
    if not sions:
        return  # Empty databases receive this when their canonical E5 master is seeded.
    if len(sions) != 1:
        raise RuntimeError("E5 configuration conflict: multiple canonical E5 SION rows exist.")
    sion = sions[0]
    profiles = list(Profile.objects.filter(sion=sion))
    if profiles or Rule.objects.filter(sion=sion).exists():
        # Stable profile key plus complete active action keys is the deterministic
        # equivalent identity; anything else is tenant configuration to preserve.
        if len(profiles) == 1 and profiles[0].stable_key == document["stable_key"] and set(
            Action.objects.filter(profile=profiles[0], is_active=True).values_list("stable_key", flat=True)
        ) == {row["stable_key"] for row in document["actions"]}:
            return
        raise RuntimeError("E5 configuration conflict: existing E5 planner configuration differs; no rows were changed.")
    profile = Profile.objects.create(sion=sion, stable_key=document["stable_key"], strategy_type=document["strategy_type"], config=document["config"], version=document["version"], is_active=True)
    rules = next(row["config"]["rules"] for row in document["actions"] if row["action_type"] == "MATCH")
    outputs = {}
    prices = {"MILK PRODUCTS": "6.50", "EGG ALBUMIN / WPC": "25.00", "WHEAT FLOUR": "0.00", "PALM KERNEL OIL": "1.80", "RBD PALMOLEIN": "1.20", "REMAINING OILS": "5.00", "DIETARY FIBRE": "3.00"}
    for priority, spec in enumerate(rules, 1):
        key = f"E5:RULE:{priority:03d}"
        Rule.objects.create(sion=sion, stable_key=key, name=f"{priority:03d} {spec['category']}", version=document["version"], expression=spec["expression"], max_unit_price=Decimal(prices[spec["category"]]), unit="kg", priority=priority, is_active=True, execution_output=spec["category"])
        outputs[key] = spec["category"]
    for spec in document["actions"]:
        config = dict(spec["config"])
        if spec["action_type"] == "MATCH": config = {**config, "rules": None, "rule_outputs": outputs}; config.pop("rules")
        Action.objects.create(profile=profile, stable_key=spec["stable_key"], action_type=spec["action_type"], priority=spec["priority"], config=config, version=document["version"], is_active=True)
    for spec in document["mappings"]:
        Mapping.objects.create(profile=profile, stable_key=spec["stable_key"], conversion_factor=Decimal("1"), unit="kg", priority=spec["priority"], config={"source": spec["source"], "output_key": spec["output_key"]}, version=document["version"], is_active=True)


class Migration(migrations.Migration):
    dependencies = [("license", "0047_durable_replan_request_state_machine")]
    operations = [migrations.RunPython(seed_e5, migrations.RunPython.noop)]
