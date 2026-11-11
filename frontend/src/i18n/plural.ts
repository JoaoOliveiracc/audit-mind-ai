/** Plural pelas regras do idioma (I18N-04). `#` no texto vira o número. */
export interface PluralForms {
  one: string
  other: string
  /** Forma explícita para 0 (pt-BR: `Intl` trata 0 como "one", mas o uso é "0 achados"). */
  zero?: string
}

const rules = new Map<string, Intl.PluralRules>()

export function plural(locale: string, n: number, forms: PluralForms): string {
  let pr = rules.get(locale)
  if (!pr) {
    pr = new Intl.PluralRules(locale)
    rules.set(locale, pr)
  }
  const form = n === 0 && forms.zero !== undefined ? forms.zero : pr.select(n) === 'one' ? forms.one : forms.other
  return form.replace(/#/g, String(n))
}
