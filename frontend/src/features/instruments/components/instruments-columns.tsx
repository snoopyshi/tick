import { type ColumnDef } from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'
import { DataTableColumnHeader } from '@/components/data-table'
import { assetTypeLabel } from '../data/data'
import { type Instrument } from '../data/schema'

export const instrumentsColumns: ColumnDef<Instrument>[] = [
  {
    accessorKey: 'symbol',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='代码' />
    ),
    cell: ({ row }) => (
      <span className='font-medium'>{row.getValue('symbol')}</span>
    ),
  },
  {
    accessorKey: 'name',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='名称' />
    ),
    meta: {
      className: 'ps-1 max-w-0 w-1/3',
      tdClassName: 'ps-4',
    },
    cell: ({ row }) => (
      <span className='truncate'>{row.getValue('name')}</span>
    ),
  },
  {
    accessorKey: 'exchange',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='交易所' />
    ),
    cell: ({ row }) => {
      const exchange = row.getValue('exchange') as string | null
      return <span>{exchange ?? '—'}</span>
    },
  },
  {
    accessorKey: 'asset_type',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='类型' />
    ),
    cell: ({ row }) => {
      const value = String(row.getValue('asset_type'))
      return (
        <Badge variant='outline' className='capitalize'>
          {assetTypeLabel[value] ?? value}
        </Badge>
      )
    },
    filterFn: (row, id, value: string[]) => {
      return value.includes(String(row.getValue(id)))
    },
  },
  {
    accessorKey: 'list_date',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='上市日期' />
    ),
    cell: ({ row }) => {
      const value = row.getValue('list_date') as string | null
      return <span>{value ?? '—'}</span>
    },
  },
  {
    accessorKey: 'currency',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='币种' />
    ),
  },
]
