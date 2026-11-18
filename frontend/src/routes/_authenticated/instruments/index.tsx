import z from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { Instruments } from '@/features/instruments'
import { assetTypes } from '@/features/instruments/data/data'

const instrumentSearchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
  filter: z.string().optional().catch(''),
  assetType: z
    .array(z.enum(assetTypes.map((item) => item.value)))
    .optional()
    .catch([]),
})

export const Route = createFileRoute('/_authenticated/instruments/')({
  validateSearch: instrumentSearchSchema,
  component: Instruments,
})
