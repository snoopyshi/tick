export const assetTypes = [
  { label: 'A 股', value: 'a-share' },
  { label: 'A 股指数', value: 'a-share-index' },
] as const

export const assetTypeLabel = Object.fromEntries(
  assetTypes.map((item) => [item.value, item.label])
) as Record<string, string>
