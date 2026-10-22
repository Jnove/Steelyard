import { Alert } from 'antd'
import { errorMessages } from '../utils/schema-form'

export function RequestErrors({ error, title = '操作未完成' }: { error: unknown; title?: string }) {
  const messages = errorMessages(error)
  if (!messages.length) return null
  return <Alert type="error" showIcon message={title} description={<ul>{messages.map((message, index) => <li key={index}>{message}</li>)}</ul>} />
}
