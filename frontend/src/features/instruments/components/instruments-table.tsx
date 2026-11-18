import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getRouteApi } from '@tanstack/react-router'
import {
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { cn } from '@/lib/utils'
import { useTableUrlState } from '@/hooks/use-table-url-state'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DataTablePagination, DataTableToolbar } from '@/components/data-table'
import { fetchInstruments } from '../api'
import { assetTypes } from '../data/data'
import { instrumentsColumns as columns } from './instruments-columns'

const route = getRouteApi('/_authenticated/instruments/')

export function InstrumentsTable() {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})

  const {
    globalFilter,
    onGlobalFilterChange,
    columnFilters,
    onColumnFiltersChange,
    pagination,
    onPaginationChange,
    ensurePageInRange,
  } = useTableUrlState({
    search: route.useSearch(),
    navigate: route.useNavigate(),
    pagination: { defaultPage: 1, defaultPageSize: 20 },
    globalFilter: { enabled: true, key: 'filter' },
    columnFilters: [
      { columnId: 'asset_type', searchKey: 'assetType', type: 'array' },
    ],
  })

  const assetTypeFilter = useMemo(() => {
    const raw = columnFilters.find((item) => item.id === 'asset_type')?.value
    return Array.isArray(raw) ? (raw as string[]) : []
  }, [columnFilters])

  const query = useQuery({
    queryKey: [
      'instruments',
      pagination.pageIndex,
      pagination.pageSize,
      globalFilter ?? '',
      assetTypeFilter,
    ],
    queryFn: () =>
      fetchInstruments({
        q: globalFilter || undefined,
        assetType: assetTypeFilter,
        limit: pagination.pageSize,
        offset: pagination.pageIndex * pagination.pageSize,
      }),
    placeholderData: (previous) => previous,
  })

  const rows = query.data?.items ?? []
  const total = query.data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / pagination.pageSize) || 1)

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: rows,
    columns,
    state: {
      sorting,
      columnVisibility,
      columnFilters,
      globalFilter,
      pagination,
    },
    manualPagination: true,
    manualFiltering: true,
    pageCount,
    rowCount: total,
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange,
    onGlobalFilterChange,
    onColumnFiltersChange,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  useEffect(() => {
    ensurePageInRange(pageCount)
  }, [pageCount, ensurePageInRange])

  return (
    <div className={cn('flex flex-1 flex-col gap-4')}>
      <DataTableToolbar
        table={table}
        searchPlaceholder='按代码或名称搜索…'
        filters={[
          {
            columnId: 'asset_type',
            title: '类型',
            options: assetTypes.map((item) => ({
              label: item.label,
              value: item.value,
            })),
          },
        ]}
      />
      <div className='overflow-hidden rounded-md border'>
        <Table className='min-w-xl'>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className={cn(header.column.columnDef.meta?.className)}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {query.isLoading && rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className='h-24 text-center'
                >
                  加载中…
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn(cell.column.columnDef.meta?.tdClassName)}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className='h-24 text-center'
                >
                  {query.isError ? '加载失败，请稍后重试。' : '暂无结果。'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} className='mt-auto' />
    </div>
  )
}
