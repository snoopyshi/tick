import type { SubmitEvent } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ConfirmDialog } from './confirm-dialog'

describe('ConfirmDialog', () => {
  it('renders title, description, and default buttons', async () => {
    const { getByRole, getByText } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='删除项目'
        desc='此操作无法撤销。'
        handleConfirm={vi.fn()}
      />
    )

    await expect
      .element(getByRole('heading', { name: '删除项目' }))
      .toBeInTheDocument()
    await expect
      .element(getByText('此操作无法撤销。'))
      .toBeInTheDocument()
    await expect
      .element(getByRole('button', { name: '取消' }))
      .toBeInTheDocument()
    await expect
      .element(getByRole('button', { name: '继续' }))
      .toBeInTheDocument()
  })

  it('calls handleConfirm when the confirm button is clicked', async () => {
    const handleConfirm = vi.fn()
    const { getByRole } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='退出登录'
        desc='确定吗？'
        confirmText='退出登录'
        handleConfirm={handleConfirm}
      />
    )

    await userEvent.click(getByRole('button', { name: '退出登录' }))
    expect(handleConfirm).toHaveBeenCalledOnce()
  })

  it('disables confirm when disabled is true', async () => {
    const handleConfirm = vi.fn()
    const { getByRole } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='危险操作'
        desc='...'
        disabled
        handleConfirm={handleConfirm}
      />
    )

    const confirm = getByRole('button', { name: '继续' })
    await expect.element(confirm).toBeDisabled()
    expect(handleConfirm).not.toHaveBeenCalled()
  })

  it('when isLoading is true, disables cancel and confirm', async () => {
    const handleConfirm = vi.fn()
    const { getByRole } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='加载中'
        desc='...'
        isLoading
        handleConfirm={handleConfirm}
      />
    )

    await expect.element(getByRole('button', { name: '取消' })).toBeDisabled()
    await expect
      .element(getByRole('button', { name: '继续' }))
      .toBeDisabled()
  })

  it('supports custom button texts', async () => {
    const { getByRole } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='删除'
        desc='...'
        cancelBtnText='否'
        confirmText='是'
        handleConfirm={vi.fn()}
      />
    )

    await expect
      .element(getByRole('button', { name: '否' }))
      .toBeInTheDocument()
    await expect
      .element(getByRole('button', { name: '是' }))
      .toBeInTheDocument()
  })

  it('renders confirm as submit button linked to desc form when `form` is set', async () => {
    const { getByRole } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='删除任务'
        form='tasks-multi-delete-form'
        desc={
          <form id='tasks-multi-delete-form' className='space-y-4'>
            <p>输入「删除」以确认。</p>
          </form>
        }
        confirmText='删除'
        destructive
      />
    )

    const deleteBtn = getByRole('button', { name: '删除' })
    await expect.element(deleteBtn).toHaveAttribute('type', 'submit')
    await expect
      .element(deleteBtn)
      .toHaveAttribute('form', 'tasks-multi-delete-form')
  })

  it('submits the desc form when confirm is clicked (form prop, no handleConfirm)', async () => {
    const onSubmit = vi.fn((e: SubmitEvent) => e.preventDefault())
    const { getByRole, getByText } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title='删除'
        form='user-delete-form'
        desc={
          <form
            id='user-delete-form'
            onSubmit={onSubmit}
            className='space-y-4'
          >
            <p>确认删除？</p>
          </form>
        }
        confirmText='删除'
        destructive
      />
    )

    await expect.element(getByText('确认删除？')).toBeInTheDocument()

    await userEvent.click(getByRole('button', { name: '删除' }))
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('does not submit the form when confirm is disabled (typed confirmation mismatch)', async () => {
    const onSubmit = vi.fn((e: SubmitEvent) => e.preventDefault())
    const { getByRole } = await render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        disabled
        title='删除'
        form='user-delete-form'
        desc={
          <form
            id='user-delete-form'
            onSubmit={onSubmit}
            className='space-y-4'
          >
            <input type='text' name='username' placeholder='username' />
          </form>
        }
        confirmText='删除'
        destructive
      />
    )

    const deleteBtn = getByRole('button', { name: '删除' })
    await expect.element(deleteBtn).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})