import { ContentSection } from '../components/content-section'
import { AccountForm } from './account-form'

export function SettingsAccount() {
  return (
    <ContentSection
      title='账户'
      desc='更新账户设置，选择首选语言与
          时区。'
    >
      <AccountForm />
    </ContentSection>
  )
}
