import { Modal } from 'antd'
import { RequestErrors } from './SchemaForm'

export default function DeleteConfirm({ kind, name, pending, error, onConfirm, onCancel }: {
  kind: '项目' | '方案'; name?: string; pending: boolean; error?: unknown;
  onConfirm: () => void; onCancel: () => void;
}) {
  return <Modal title={`删除${kind}`} open={name !== undefined} okText="确认删除" cancelText="取消"
    okButtonProps={{ danger: true }} cancelButtonProps={{ disabled: pending }} confirmLoading={pending}
    closable={!pending} keyboard={!pending} maskClosable={false} onOk={onConfirm}
    onCancel={() => { if (!pending) onCancel() }}>
    <p>确定删除{kind}「{name}」吗？此操作无法撤销。</p>
    <p>{kind === '项目' ? '该项目下的全部方案、评估结果和报告缓存也会一并删除。'
      : '该方案的评估结果将删除，项目的排名和报告缓存将清空。已有推演副本会保留，并解除与原方案的关联。'}</p>
    <RequestErrors error={error} title="删除未完成" />
  </Modal>
}
