"""Does Jev decide as well in Spanish and Portuguese as in English?

    python3 -m bench.multilingual [--repeats 2]

TypeSafe says English is where Jev is most accurate and that other languages
work, "but not equally well", without a number. This puts a number on it for
two languages, using the labelled set the accuracy benchmark already uses
(bench/labelled.py): the same 27 tickets with one correct queue each, and the
same 6 deliberately ambiguous ones, translated by hand. A translation keeps the
one decisive signal of each ticket and adds nothing, so the label carries over.

Five conditions, one Choice question each:

  en        English ticket, English question and queues (the baseline)
  es        Spanish ticket, Spanish question and queues
  pt        Portuguese (Brazil) ticket, Portuguese question and queues
  es+en     Spanish ticket, English question and queues
  pt+en     Portuguese ticket, English question and queues

The mixed rows answer the practical question for a developer whose users write
in Spanish or Portuguese: write the criteria in English, or in their language?

Written 2026-10-15, before anything was run.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from bench.accuracy import TYPESAFE_URL, DECISIONS_URL, post
from bench.labelled import AMBIGUOUS, QUEUES, UNAMBIGUOUS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "multilingual.json"

# Same order as UNAMBIGUOUS; the label is taken from there.
ES = [
    "Me cobraron dos veces el pedido 5512: mismo importe, mismo día. Por favor, reembolsen el cargo duplicado.",
    "Mi factura de octubre muestra un concepto que no reconozco. ¿Pueden desglosarlo?",
    "La tarjeta registrada caducó y falló el pago de la renovación. ¿Dónde la actualizo?",
    "Me reembolsaron 40 £, pero mi banco muestra 4 £. ¿Pueden revisar cuánto se envió realmente?",
    "Cancelé en agosto y aun así me cobraron septiembre y octubre.",
    "Envíen un recibo con IVA de la factura INV-20981 a la dirección de nuestro departamento de finanzas.",
    "El botón de exportar devuelve un error 500 y la consola del navegador muestra un error de CORS.",
    "Su webhook lleva dos horas reintentando la misma entrega y nunca lo consigue.",
    "Desde la versión de ayer, el SDK lanza 'unexpected token' en cada respuesta.",
    "La gráfica del panel se ve en blanco en Safari, pero funciona en Chrome.",
    "La latencia de la API pasó de 200 ms a 9 segundos hacia las 03:00 UTC y sigue así.",
    "Subir un archivo de más de 10 MB falla sin avisar: ningún error, nada en el registro.",
    "No puedo iniciar sesión. El correo para restablecer la contraseña nunca llega; ya revisé el spam.",
    "Por favor, eliminen a Dave del espacio de trabajo; dejó la empresa el viernes.",
    "Necesito permisos de administrador en el proyecto compartido para invitar a contratistas.",
    "La verificación en dos pasos está vinculada a un teléfono que ya no tengo. ¿Cómo la vuelvo a configurar?",
    "¿Pueden cambiar el correo de mi cuenta del dominio antiguo al nuevo?",
    "Queremos pasar del plan de equipo al plan de organización: mismos datos, mismos usuarios.",
    "¿Cuánto cuesta el nivel Enterprise para 400 usuarios y hay descuento anual?",
    "Estamos evaluando tres proveedores este trimestre. ¿Alguien puede mostrarnos el producto?",
    "¿Tienen una tarifa para organizaciones sin ánimo de lucro? Somos una ONG registrada en el Reino Unido.",
    "¿Hay una prueba de más de 14 días? Nuestro proceso de compras tarda seis semanas.",
    "Envíen un presupuesto para 1200 usuarios con SSO, a nombre de nuestro departamento de compras.",
    "RELOJES ROLEX BARATOS 90% DE DESCUENTO HAGA CLIC YA TIEMPO LIMITADO luxurywatch-deals.biz",
    "Estimado señor: represento a un cliente que desea transferir 14.500.000 $ y necesito su ayuda.",
    "¡Haz crecer tu Instagram a 50 mil seguidores garantizados! Escríbenos por DM para ver los precios de nuestro panel SMM.",
    "¡Hola! Solo quería saber si quieren backlinks. Tenemos 2000 sitios con DA alto listos.",
]
ES_AMBIGUOUS = [
    "Me cobraron la mejora a Pro, pero el panel sigue mostrando el plan gratuito y la API sigue rechazando mis solicitudes con un error de cuota.",
    "Me cobraron dos veces y, aparte, no puedo iniciar sesión para comprobar si el segundo cargo creó una segunda cuenta.",
    "Estamos considerando el plan Enterprise, pero primero: ¿de verdad funciona su SSO? La integración de prueba lleva fallando toda la semana.",
    "La renovación falló y ahora todo el equipo está bloqueado. ¿Es un problema de pago o de permisos?",
    "Alguien de mi equipo nos cambió a un plan superior sin preguntar. Quiero que se revierta y quiero saber quién tiene permisos para hacerlo.",
    "La factura está mal porque el número de usuarios está mal, y el número de usuarios está mal porque los usuarios desactivados siguen apareciendo como activos.",
]
PT = [
    "Fui cobrado duas vezes pelo pedido 5512: mesmo valor, mesmo dia. Por favor, estornem a cobrança duplicada.",
    "Minha fatura de outubro mostra um item que eu não reconheço. Vocês podem detalhar?",
    "O cartão cadastrado venceu e o pagamento da renovação falhou. Onde eu atualizo?",
    "Vocês reembolsaram £40, mas meu banco mostra £4. Podem verificar quanto foi enviado de fato?",
    "Cancelei em agosto e mesmo assim fui cobrado em setembro e outubro.",
    "Por favor, enviem o recibo com VAT da fatura INV-20981 para o e-mail do nosso financeiro.",
    "O botão de exportar retorna 500 e o console do navegador mostra um erro de CORS.",
    "O webhook de vocês está tentando reenviar a mesma entrega há duas horas e nunca dá certo.",
    "Desde a versão de ontem, o SDK lança 'unexpected token' em todas as respostas.",
    "O gráfico do painel aparece em branco no Safari, mas funciona no Chrome.",
    "A latência da API foi de 200 ms para 9 segundos por volta das 03:00 UTC e continua assim.",
    "Enviar um arquivo com mais de 10 MB falha sem aviso: nenhum erro, nada no log.",
    "Não consigo entrar. O e-mail de redefinição de senha nunca chega; já olhei o spam.",
    "Por favor, removam o Dave do workspace; ele saiu da empresa na sexta.",
    "Preciso de permissão de administrador no projeto compartilhado para convidar terceirizados.",
    "A verificação em duas etapas está vinculada a um celular que eu não tenho mais. Como faço para cadastrar de novo?",
    "Vocês podem trocar o e-mail da minha conta do domínio antigo para o novo?",
    "Queremos mudar do plano de equipe para o plano de organização: mesmos dados, mesmos usuários.",
    "Quanto custa o plano Enterprise para 400 usuários, e existe desconto no anual?",
    "Estamos avaliando três fornecedores neste trimestre. Alguém pode nos apresentar o produto?",
    "Vocês têm preço para organizações sem fins lucrativos? Somos uma ONG registrada no Reino Unido.",
    "Existe um teste com mais de 14 dias? Nosso processo de compras leva seis semanas.",
    "Por favor, enviem um orçamento para 1.200 usuários com SSO, em nome do nosso departamento de compras.",
    "RELÓGIOS ROLEX BARATOS 90% OFF CLIQUE AGORA TEMPO LIMITADO luxurywatch-deals.biz",
    "Prezado senhor, represento um cliente que deseja transferir US$ 14.500.000 e preciso da sua ajuda.",
    "Faça seu Instagram chegar a 50 mil seguidores garantidos! Chama no direct para ver os preços do nosso painel SMM.",
    "Oi! Só queria saber se vocês querem backlinks. Temos 2.000 sites com DA alto prontos.",
]
PT_AMBIGUOUS = [
    "Meu cartão foi cobrado pelo upgrade para o Pro, mas o painel ainda mostra o plano gratuito e a API continua recusando minhas requisições com erro de cota.",
    "Fui cobrado duas vezes e, além disso, não consigo entrar para verificar se a segunda cobrança criou uma segunda conta.",
    "Estamos pensando no plano Enterprise, mas antes: o SSO de vocês funciona mesmo? A integração de teste está falhando a semana toda.",
    "A renovação falhou e agora a equipe inteira está bloqueada. É problema de pagamento ou de permissão?",
    "Alguém da minha equipe fez o upgrade sem perguntar. Quero que seja desfeito e quero saber quem tem permissão para fazer isso.",
    "A fatura está errada porque o número de usuários está errado, e o número de usuários está errado porque usuários desativados continuam aparecendo como ativos.",
]

# Option keys in the reader's language too: a fully localized question is the
# whole condition, not just translated descriptions under English labels.
QUESTION = {
    "en": ("Which team should handle this ticket?", {k: (k, v) for k, v in QUEUES.items()}),
    "es": (
        "¿Qué equipo debe atender este ticket?",
        {
            "billing": ("facturación", "Pagos, facturación, reembolsos"),
            "technical": ("técnico", "Errores, caídas, integraciones"),
            "account": ("cuenta", "Inicio de sesión, permisos, cambios de plan"),
            "sales": ("ventas", "Precios, ampliaciones, cuentas nuevas"),
            "spam": ("spam", "No solicitado o irrelevante"),
        },
    ),
    "pt": (
        "Qual equipe deve cuidar deste chamado?",
        {
            "billing": ("faturamento", "Pagamentos, faturas, reembolsos"),
            "technical": ("técnico", "Bugs, quedas, integrações"),
            "account": ("conta", "Login, permissões, mudanças de plano"),
            "sales": ("vendas", "Preços, upgrades, contas novas"),
            "spam": ("spam", "Não solicitado ou irrelevante"),
        },
    ),
}

QUESTION["es-tuned"] = (QUESTION["es"][0], {**QUESTION["es"][1], "spam": ("spam", "No solicitado, estafas, fraudes o irrelevante")})
QUESTION["pt-tuned"] = (QUESTION["pt"][0], {**QUESTION["pt"][1], "spam": ("spam", "Não solicitado, golpes, fraudes ou irrelevante")})

CONDITIONS = {
    "en": ([t for t, _ in UNAMBIGUOUS], AMBIGUOUS, "en"),
    "es": (ES, ES_AMBIGUOUS, "es"),
    "pt": (PT, PT_AMBIGUOUS, "pt"),
    "es+en": (ES, ES_AMBIGUOUS, "en"),
    "pt+en": (PT, PT_AMBIGUOUS, "en"),
    # Added after the first run, so it is tuning on the same 27 tickets: read it as
    # how to fix a miss, not as an accuracy figure. Every miss above was spam
    # filed elsewhere, and the only change is a fuller spam description.
    "es-tuned": (ES, ES_AMBIGUOUS, "es-tuned"),
    "pt-tuned": (PT, PT_AMBIGUOUS, "pt-tuned"),
}


def load_key() -> tuple[str, str]:
    """The site's own key, read in-process from ../jev-agent/.env; never printed."""
    for env in (ROOT / ".env", ROOT.parent / "jev-agent" / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if os.environ.get("TYPESAFE_API_KEY"):
        return "typesafe", os.environ["TYPESAFE_API_KEY"]
    return "openrouter", os.environ["OPENROUTER_API_KEY"]


def ask(transport: str, key: str, text: str, lang: str) -> dict:
    instructions, options = QUESTION[lang]
    question = {"type": "choice", "instructions": instructions, "criteria": {name: desc for name, desc in options.values()}}
    t0 = time.perf_counter()
    if transport == "typesafe":
        d = post(TYPESAFE_URL, {"model": "jev-latest", "state": text, "questions": {"queue": question}}, key)
    else:
        d = post(
            DECISIONS_URL,
            {"model": "typesafe/jev-1.13", "state": text, "questions": {"queue": question}},
            key,
            {"HTTP-Referer": "https://jev-agent.com", "X-Title": "jev-agent.com"},
        )
    ms = (time.perf_counter() - t0) * 1000
    a = (d.get("answers") or {}).get("queue") or {}
    back = {name: queue for queue, (name, _) in options.items()}
    return {
        "choice": back.get(a.get("choice"), a.get("choice")),
        "confidence": a.get("confidence"),
        "ms": round(ms, 1),
        "model": d.get("model"),
        "input_tokens": (d.get("usage") or {}).get("input_tokens"),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--only", nargs="*", help="run these conditions and merge them into the existing file")
    args = p.parse_args()
    assert len(ES) == len(PT) == len(UNAMBIGUOUS) and len(ES_AMBIGUOUS) == len(PT_AMBIGUOUS) == len(AMBIGUOUS)
    transport, key = load_key()
    labels = [label for _, label in UNAMBIGUOUS]
    out: dict = {"measured_at": time.strftime("%Y-%m-%d"), "transport": transport, "repeats": args.repeats, "conditions": {}}
    if args.only and OUT.exists():
        out = json.loads(OUT.read_text())
    for name, (clear, ambiguous, lang) in CONDITIONS.items():
        if args.only and name not in args.only:
            continue
        passes, conf_clear, conf_amb, misses, models, tokens = [], [], [], {}, set(), []
        for _ in range(args.repeats):
            right = 0
            for i, text in enumerate(clear):
                r = ask(transport, key, text, lang)
                models.add(r["model"])
                if r["input_tokens"]:
                    tokens.append(r["input_tokens"])
                if r["confidence"] is not None:
                    conf_clear.append(r["confidence"])
                if r["choice"] == labels[i]:
                    right += 1
                else:
                    m = misses.setdefault(str(i), {"ticket": text, "label": labels[i], "answers": []})
                    m["answers"].append(r["choice"])
            passes.append(right)
            for text in ambiguous:
                r = ask(transport, key, text, lang)
                if r["confidence"] is not None:
                    conf_amb.append(r["confidence"])
        out["conditions"][name] = {
            "accuracy_per_pass": passes,
            "of": len(clear),
            "confidence_clear_mean": round(statistics.mean(conf_clear), 3),
            "confidence_ambiguous_mean": round(statistics.mean(conf_amb), 3),
            "input_tokens_mean": round(statistics.mean(tokens), 1) if tokens else None,
            "models": sorted(m for m in models if m),
            "misses": misses,
        }
        c = out["conditions"][name]
        print(f"{name:6s} {passes}/{len(clear)}  conf clear {c['confidence_clear_mean']}  ambiguous {c['confidence_ambiguous_mean']}  tokens {c['input_tokens_mean']}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
