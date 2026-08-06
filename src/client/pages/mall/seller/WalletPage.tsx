import { useCallback, useEffect, useState } from 'react'
import { App, Button, Descriptions, Form, Input, InputNumber, Modal, Table, Tag } from 'antd'
import {
  getSellerWallet,
  listSellerLedger,
  listSellerWithdrawals,
  requestMallWithdraw,
} from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import { formatFen } from '../../../lib/mallFormat'
import type { MallWallet, MallWalletLedger, MallWithdraw } from '../../../lib/types'

const LEDGER_TYPE_LABELS: Record<string, string> = {
  sale: '销售货款',
  withdraw: '提现',
  deposit: '保证金',
}

const LEDGER_STATUS_LABELS: Record<string, { text: string; color: string }> = {
  frozen: { text: '冻结中', color: 'blue' },
  available: { text: '已入账', color: 'green' },
  withdrawn: { text: '已扣除', color: 'default' },
}

const WITHDRAW_STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '处理中', color: 'orange' },
  approved: { text: '已通过', color: 'blue' },
  rejected: { text: '已驳回', color: 'red' },
  paid: { text: '已打款', color: 'green' },
}

export default function WalletPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [wallet, setWallet] = useState<MallWallet | null>(null)
  const [ledger, setLedger] = useState<MallWalletLedger[]>([])
  const [ledgerTotal, setLedgerTotal] = useState(0)
  const [ledgerPage, setLedgerPage] = useState(1)
  const [withdrawals, setWithdrawals] = useState<MallWithdraw[]>([])
  const [withdrawTotal, setWithdrawTotal] = useState(0)
  const [withdrawPage, setWithdrawPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [withdrawOpen, setWithdrawOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [walletData, ledgerData, withdrawData] = await Promise.all([
        getSellerWallet(),
        listSellerLedger({ page: ledgerPage, page_size: 10 }),
        listSellerWithdrawals({ page: withdrawPage, page_size: 10 }),
      ])
      setWallet(walletData)
      setLedger(ledgerData.items)
      setLedgerTotal(ledgerData.total)
      setWithdrawals(withdrawData.items)
      setWithdrawTotal(withdrawData.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '钱包加载失败'))
    } finally {
      setLoading(false)
    }
  }, [ledgerPage, withdrawPage, message])

  useEffect(() => {
    load()
  }, [load])

  const submitWithdraw = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await requestMallWithdraw({
        amount_fen: values.amount_fen,
        account_info: { account: values.account, holder: values.holder ?? '' },
      })
      message.success('提现申请已提交，等待管理员处理')
      setWithdrawOpen(false)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提现申请失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const ledgerColumns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '类型',
      dataIndex: 'entry_type',
      key: 'entry_type',
      render: (t: MallWalletLedger['entry_type']) => LEDGER_TYPE_LABELS[t] ?? t,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: MallWalletLedger['status']) => {
        const label = LEDGER_STATUS_LABELS[s]
        return <Tag color={label?.color}>{label?.text ?? s}</Tag>
      },
    },
    {
      title: '金额',
      dataIndex: 'amount_fen',
      key: 'amount_fen',
      render: (fen: number) => (
        <span style={{ color: fen >= 0 ? '#52c41a' : '#F31947' }}>
          {fen >= 0 ? '+' : '-'}¥{formatFen(Math.abs(fen))}
        </span>
      ),
    },
    {
      title: '说明',
      dataIndex: 'note',
      key: 'note',
      render: (note: string | null, record: MallWalletLedger) => note ?? record.related_no ?? '-',
    },
  ]

  const withdrawColumns = [
    { title: '单号', dataIndex: 'withdraw_no', key: 'withdraw_no' },
    { title: '申请时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '金额',
      dataIndex: 'amount_fen',
      key: 'amount_fen',
      render: (fen: number) => <b style={{ color: '#F31947' }}>¥{formatFen(fen)}</b>,
    },
    {
      title: '收款信息',
      dataIndex: 'account_info',
      key: 'account_info',
      render: (info: Record<string, string>) => `${info.holder ?? ''} ${info.account ?? ''}`.trim() || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: MallWithdraw['status']) => {
        const label = WITHDRAW_STATUS_LABELS[s]
        return <Tag color={label?.color}>{label?.text ?? s}</Tag>
      },
    },
    {
      title: '处理时间',
      dataIndex: 'handled_at',
      key: 'handled_at',
      render: (v: string | null) => v ?? '-',
    },
  ]

  return (
    <div className="space-y-4">
      <section className="rounded bg-white" style={{ padding: '20px 24px' }}>
        <h3 className="text-base font-bold mb-4" style={{ color: '#333' }}>
          店铺资金
        </h3>
        {wallet ? (
          <Descriptions column={4}>
            <Descriptions.Item label="可用余额">
              <b className="text-lg" style={{ color: '#F31947' }}>¥{formatFen(wallet.available_fen)}</b>
            </Descriptions.Item>
            <Descriptions.Item label="冻结货款">¥{formatFen(wallet.frozen_fen)}</Descriptions.Item>
            <Descriptions.Item label="保证金">¥{formatFen(wallet.deposit_fen)}</Descriptions.Item>
            <Descriptions.Item label="累计总额">¥{formatFen(wallet.total_fen)}</Descriptions.Item>
          </Descriptions>
        ) : (
          <div className="text-sm" style={{ color: '#999' }}>
            暂无资金数据
          </div>
        )}
        <Button type="primary" className="mt-4" disabled={!wallet || wallet.available_fen <= 0} onClick={() => setWithdrawOpen(true)} style={{ background: '#F31947' }}>
          申请提现
        </Button>
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h4 className="text-sm font-bold mb-3" style={{ color: '#333' }}>
          资金流水
        </h4>
        <Table
          rowKey="id"
          columns={ledgerColumns}
          dataSource={ledger}
          loading={loading}
          size="small"
          pagination={{ current: ledgerPage, pageSize: 10, total: ledgerTotal, onChange: setLedgerPage, showSizeChanger: false }}
        />
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h4 className="text-sm font-bold mb-3" style={{ color: '#333' }}>
          提现记录
        </h4>
        <Table
          rowKey="id"
          columns={withdrawColumns}
          dataSource={withdrawals}
          loading={loading}
          size="small"
          pagination={{ current: withdrawPage, pageSize: 10, total: withdrawTotal, onChange: setWithdrawPage, showSizeChanger: false }}
        />
      </section>

      <Modal
        title="申请提现"
        open={withdrawOpen}
        onCancel={() => setWithdrawOpen(false)}
        onOk={submitWithdraw}
        confirmLoading={submitting}
        okText="提交申请"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="amount_fen" label="提现金额（分）" rules={[{ required: true, message: '请输入提现金额' }]}>
            <InputNumber
              min={1}
              max={wallet?.available_fen ?? 0}
              style={{ width: '100%' }}
              placeholder={`可用余额 ¥${wallet ? formatFen(wallet.available_fen) : '0.00'}`}
            />
          </Form.Item>
          <Form.Item name="account" label="收款账号" rules={[{ required: true, message: '请输入收款账号' }]}>
            <Input placeholder="支付宝 / 银行卡号" />
          </Form.Item>
          <Form.Item name="holder" label="收款人姓名" rules={[{ required: true, message: '请输入收款人姓名' }]}>
            <Input placeholder="真实姓名" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
