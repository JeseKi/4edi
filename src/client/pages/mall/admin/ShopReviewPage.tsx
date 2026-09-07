import { useCallback, useEffect, useState } from 'react'
import { App, Button, Checkbox, Descriptions, Form, Image, Input, Modal, Popconfirm, Space, Table, Tabs, Tag } from 'antd'
import {
  approveAdminShop,
  archiveAdminShopAgreement,
  closeAdminShop,
  generateAdminShopAgreement,
  listAdminShops,
  reopenAdminShop,
  reviewAdminShop,
  submitAdminPlatformSignedAgreement,
} from '../../../lib/sellerMall'
import api from '../../../lib/api'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { FileAsset, MallShop, MallShopStatus, ShopOnboardingStage } from '../../../lib/types'
import FileUpload from '../../../components/files/FileUpload'

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '入驻处理中', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
  closed: { text: '已关闭', color: 'default' },
}

const STAGE_LABELS: Record<ShopOnboardingStage, { text: string; color: string }> = {
  qualification_submitted: { text: '资质待预审', color: 'orange' },
  qualification_preapproved: { text: '资质预审通过', color: 'blue' },
  agreement_generated: { text: '协议已生成', color: 'cyan' },
  merchant_signed: { text: '商家已签署', color: 'geekblue' },
  platform_signed: { text: '平台已签署', color: 'purple' },
  agreement_archived: { text: '最终协议已归档', color: 'magenta' },
  approved: { text: '商家审核通过', color: 'green' },
  rejected: { text: '资质已驳回', color: 'red' },
}

function stageLabel(shop: MallShop): { text: string; color: string } {
  if (shop.current_agreement?.signature_mode === 'online_click') {
    if (shop.onboarding_stage === 'agreement_generated') {
      return { text: '等待商家在线签约', color: 'cyan' }
    }
    if (shop.onboarding_stage === 'agreement_archived') {
      return { text: '商家已在线签约', color: 'magenta' }
    }
  }
  return STAGE_LABELS[shop.onboarding_stage]
}

const TABS = [
  { key: 'pending', label: '入驻处理中' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已驳回' },
  { key: 'closed', label: '已关闭' },
  { key: 'expiring_soon', label: '30 天内到期' },
  { key: 'expired', label: '已过期' },
  { key: '', label: '全部' },
]

export default function ShopReviewPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [platformForm] = Form.useForm()
  const [status, setStatus] = useState<MallShopStatus | 'expiring_soon' | 'expired' | ''>('pending')
  const [page, setPage] = useState(1)
  const [shops, setShops] = useState<MallShop[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [reviewTarget, setReviewTarget] = useState<MallShop | null>(null)
  const [reviewApproved, setReviewApproved] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [documentPreview, setDocumentPreview] = useState<{ title: string; url: string; contentType: string; filename: string } | null>(null)
  const [evidenceUploaded, setEvidenceUploaded] = useState(false)
  const [platformSignTarget, setPlatformSignTarget] = useState<MallShop | null>(null)
  const [platformFileUploaded, setPlatformFileUploaded] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qualificationState = status === 'expiring_soon' || status === 'expired' ? status : undefined
      const result = await listAdminShops({
        status: qualificationState ? undefined : (status || undefined) as MallShopStatus | undefined,
        qualification_state: qualificationState,
        page,
        page_size: 10,
      })
      setShops(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '店铺列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [status, page, message])

  useEffect(() => {
    setPage(1)
  }, [status])

  useEffect(() => {
    load()
  }, [load])

  const submitReview = async () => {
    if (!reviewTarget) return
    const values = await form.validateFields()
    const checklistFields = [
      'entity_name_matches',
      'credit_code_matches',
      'legal_representative_matches',
      'registration_status_valid',
      'registered_address_matches',
      'business_scope_matches',
    ]
    if (reviewApproved && checklistFields.some((field) => !values[field])) {
      message.error('通过审核前必须确认全部企业核验项目一致')
      return
    }
    setSubmitting(true)
    try {
      await reviewAdminShop(reviewTarget.id, {
        approved: reviewApproved,
        reject_reason: reviewApproved ? undefined : values.reject_reason,
        evidence_asset_id: values.evidence_asset_id,
        registration_status: values.registration_status,
        verification_source: values.verification_source,
        entity_name_matches: Boolean(values.entity_name_matches),
        credit_code_matches: Boolean(values.credit_code_matches),
        legal_representative_matches: Boolean(values.legal_representative_matches),
        registration_status_valid: Boolean(values.registration_status_valid),
        registered_address_matches: Boolean(values.registered_address_matches),
        business_scope_matches: Boolean(values.business_scope_matches),
        note: values.note,
      })
      message.success(reviewApproved ? '企业资质预审已通过，电子协议已自动生成' : '店铺资质已驳回')
      setReviewTarget(null)
      setEvidenceUploaded(false)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const generateAgreement = async (shop: MallShop) => {
    setSubmitting(true)
    try {
      await generateAdminShopAgreement(shop.id)
      message.success('协议定稿已生成，等待商家签署')
      await load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '协议生成失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const submitPlatformSignature = async () => {
    if (!platformSignTarget) return
    const values = await platformForm.validateFields()
    setSubmitting(true)
    try {
      await submitAdminPlatformSignedAgreement(platformSignTarget.id, {
        platform_signed_asset_id: values.platform_signed_asset_id,
        agreement_matches: Boolean(values.agreement_matches),
      })
      message.success('平台签署文件已提交，下一步请归档最终协议')
      setPlatformSignTarget(null)
      setPlatformFileUploaded(false)
      platformForm.resetFields()
      await load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '平台签署提交失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const archiveAgreement = async (shop: MallShop) => {
    setSubmitting(true)
    try {
      await archiveAdminShopAgreement(shop.id)
      message.success('最终协议已归档，下一步可完成商家审核')
      await load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '协议归档失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const approveShop = async (shop: MallShop) => {
    setSubmitting(true)
    try {
      await approveAdminShop(shop.id)
      message.success('商家审核已通过')
      await load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '最终审核失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const closeShop = async (shop: MallShop) => {
    try {
      await closeAdminShop(shop.id)
      message.success('店铺已关闭，其商品已全部下架')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '关闭失败'))
    }
  }

  const reopenShop = async (shop: MallShop) => {
    try {
      await reopenAdminShop(shop.id)
      message.success('店铺已开启；商品仍保持下架，需商家自行上架')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '开启失败'))
    }
  }

  const previewDocument = async (title: string, assetId: string | null) => {
    if (!assetId) return
    try {
      const [{ data: asset }, { data }] = await Promise.all([
        api.get<FileAsset>(`/files/${assetId}`),
        api.get<Blob>(`/files/${assetId}/download`, { responseType: 'blob' }),
      ])
      setDocumentPreview({
        title,
        url: URL.createObjectURL(data),
        contentType: data.type,
        filename: asset.original_filename,
      })
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '材料加载失败'))
    }
  }

  const downloadDocumentPreview = () => {
    if (!documentPreview) return
    const anchor = document.createElement('a')
    anchor.href = documentPreview.url
    anchor.download = documentPreview.filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  }

  const closeDocumentPreview = () => {
    if (documentPreview) URL.revokeObjectURL(documentPreview.url)
    setDocumentPreview(null)
  }

  const columns = [
    { title: '店铺名称', dataIndex: 'name', key: 'name' },
    { title: '店主 ID', dataIndex: 'owner_user_id', key: 'owner_user_id' },
    { title: '简介', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '保证金',
      dataIndex: 'deposit_fen',
      key: 'deposit_fen',
      render: (fen: number) => `¥${(fen / 100).toFixed(2)}`,
    },
    { title: '申请时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '状态',
      dataIndex: 'onboarding_stage',
      key: 'status',
      render: (stage: ShopOnboardingStage, record: MallShop) => {
        const label = record.status === 'closed' ? STATUS_LABELS.closed : stageLabel(record)
        return <Tag color={label?.color}>{label?.text ?? stage}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: MallShop) => (
        <div className="flex gap-1">
          {record.status === 'pending' && record.onboarding_stage === 'qualification_submitted' && (
            <>
              <Button size="small" type="primary" onClick={() => { setReviewApproved(true); setReviewTarget(record) }}>
                资质预审通过
              </Button>
              <Button size="small" danger onClick={() => { setReviewApproved(false); setReviewTarget(record) }}>
                驳回
              </Button>
            </>
          )}
          {record.status === 'pending' && record.onboarding_stage === 'qualification_preapproved' && (
            <Popconfirm title="这是升级前遗留记录，将按当前商家资料生成电子协议，确定？" onConfirm={() => void generateAgreement(record)}>
              <Button size="small" type="primary" loading={submitting}>生成电子协议</Button>
            </Popconfirm>
          )}
          {record.status === 'pending' && record.onboarding_stage === 'agreement_generated' && (
            <Space size="small" wrap>
              <span className="text-xs text-gray-500">
                {record.current_agreement?.signature_mode === 'online_click' ? '等待商家在线签约' : '等待商家上传签署文件'}
              </span>
              <Button size="small" href={`/mall/admin/shops/${record.id}/agreement/print`} target="_blank">
                {record.current_agreement?.signature_mode === 'online_click' ? '查看电子协议' : '查看协议正文'}
              </Button>
            </Space>
          )}
          {record.status === 'pending' && record.onboarding_stage === 'merchant_signed' && record.current_agreement?.signature_mode === 'uploaded_document' && (
            <Button size="small" type="primary" onClick={() => setPlatformSignTarget(record)}>提交平台签署</Button>
          )}
          {record.status === 'pending' && record.onboarding_stage === 'platform_signed' && record.current_agreement?.signature_mode === 'uploaded_document' && (
            <Popconfirm title="确认将平台签署文件作为双方最终协议归档？" onConfirm={() => void archiveAgreement(record)}>
              <Button size="small" type="primary" loading={submitting}>归档最终协议</Button>
            </Popconfirm>
          )}
          {record.status === 'pending' && record.onboarding_stage === 'agreement_archived' && (
            <>
              {record.current_agreement?.signature_mode === 'online_click' && (
                <Button size="small" href={`/mall/admin/shops/${record.id}/agreement/print`} target="_blank">查看电子协议</Button>
              )}
              <Popconfirm title="确认资质和签约记录均完整，批准商家入驻？" onConfirm={() => void approveShop(record)}>
                <Button size="small" type="primary" loading={submitting}>最终审核通过</Button>
              </Popconfirm>
            </>
          )}
          {record.status === 'approved' && (
            <>
              {record.current_agreement?.signature_mode === 'online_click' && (
                <Button size="small" href={`/mall/admin/shops/${record.id}/agreement/print`} target="_blank">查看电子协议</Button>
              )}
              <Popconfirm title="关闭店铺后其商品将全部下架，确定？" onConfirm={() => closeShop(record)}>
                <Button size="small" danger>
                  关闭店铺
                </Button>
              </Popconfirm>
            </>
          )}
          {record.status === 'closed' && (
            <Popconfirm title="开启店铺后，商品仍保持下架，确定？" onConfirm={() => reopenShop(record)}>
              <Button size="small" type="primary">
                开启店铺
              </Button>
            </Popconfirm>
          )}
          {record.status === 'rejected' && (
            <span className="text-xs" style={{ color: '#999' }}>
              {record.reject_reason || '-'}
            </span>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        店铺审核
      </h3>
      <Tabs
        activeKey={status}
        items={TABS}
        onChange={(key) => setStatus(key as MallShopStatus | 'expiring_soon' | 'expired' | '')}
        className="mb-2"
      />

      <Table
        rowKey="id"
        columns={columns}
        dataSource={shops}
        loading={loading}
        expandable={{
          expandedRowRender: (record: MallShop) => (
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="经营者姓名">{record.real_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="身份证号">{record.identity_number_masked || '-'}</Descriptions.Item>
              <Descriptions.Item label="企业法定全称">{record.legal_entity_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="统一社会信用代码">{record.unified_social_credit_code || '-'}</Descriptions.Item>
              <Descriptions.Item label="法定代表人">{record.legal_representative || '-'}</Descriptions.Item>
              <Descriptions.Item label="注册地址">{record.registered_address || '-'}</Descriptions.Item>
              <Descriptions.Item label="实际经营地址">{record.business_address || '-'}</Descriptions.Item>
              <Descriptions.Item label="营业执照有效期">{record.business_license_long_term ? '长期有效' : record.business_license_valid_until || '-'}</Descriptions.Item>
              <Descriptions.Item label="入驻阶段"><Tag color={stageLabel(record).color}>{stageLabel(record).text}</Tag></Descriptions.Item>
              <Descriptions.Item label="审核材料">
                <div className="flex flex-wrap gap-2">
                  <Button size="small" disabled={!record.business_license_asset_id} onClick={() => void previewDocument('营业执照', record.business_license_asset_id)}>
                    营业执照
                  </Button>
                  <Button size="small" disabled={!record.identity_front_asset_id} onClick={() => void previewDocument('身份证正面', record.identity_front_asset_id)}>
                    身份证正面
                  </Button>
                  <Button size="small" disabled={!record.identity_back_asset_id} onClick={() => void previewDocument('身份证反面', record.identity_back_asset_id)}>
                    身份证反面
                  </Button>
                </div>
              </Descriptions.Item>
              {record.current_agreement && (
                <Descriptions.Item label="入驻协议">
                  {record.current_agreement.signature_mode === 'online_click' ? (
                    <div className="space-y-2">
                      <div>编号：{record.current_agreement.agreement_number}；版本：{record.current_agreement.document_version}</div>
                      <div>签约方式：商家在线确认</div>
                      <div>签约账号：{record.current_agreement.merchant_signed_by_user_id ? `用户 #${record.current_agreement.merchant_signed_by_user_id}` : '等待商家签约'}</div>
                      <div>签约时间：{record.current_agreement.merchant_signed_at || '等待商家签约'}</div>
                      <Button size="small" href={`/mall/admin/shops/${record.id}/agreement/print`} target="_blank">查看电子协议</Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div>历史文件协议；编号：{record.current_agreement.agreement_number}；版本：{record.current_agreement.document_version}</div>
                      <div style={{ wordBreak: 'break-all' }}>协议定稿内部校验值：{record.current_agreement.draft_content_sha256}</div>
                      <div style={{ wordBreak: 'break-all' }}>最终归档文件校验值：{record.current_agreement.final_file_sha256 || '归档后生成'}</div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="small" disabled={!record.current_agreement.merchant_signed_asset_id} onClick={() => void previewDocument('商家签署协议', record.current_agreement?.merchant_signed_asset_id || null)}>商家签署文件</Button>
                        <Button size="small" disabled={!record.current_agreement.platform_signed_asset_id} onClick={() => void previewDocument('平台签署协议', record.current_agreement?.platform_signed_asset_id || null)}>平台签署文件</Button>
                        <Button size="small" disabled={!record.current_agreement.final_asset_id} onClick={() => void previewDocument('最终归档协议', record.current_agreement?.final_asset_id || null)}>最终归档文件</Button>
                      </div>
                    </div>
                  )}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="驳回原因">{record.reject_reason || '-'}</Descriptions.Item>
              <Descriptions.Item label="审核通过时间">{record.approved_at || '-'}</Descriptions.Item>
            </Descriptions>
          ),
        }}
        pagination={{ current: page, pageSize: 10, total, onChange: setPage, showSizeChanger: false }}
      />

      <Modal
        title={reviewApproved ? '通过企业资质预审' : '驳回企业资质'}
        open={reviewTarget != null}
        onCancel={() => setReviewTarget(null)}
        onOk={submitReview}
        confirmLoading={submitting}
        okText="确认"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          className="mt-4"
          initialValues={{ verification_source: '国家企业信用信息公示系统' }}
        >
          <Form.Item name="verification_source" label="核验来源" rules={[{ required: true, message: '请填写核验来源' }]}><Input /></Form.Item>
          <Form.Item name="registration_status" label="企业登记状态" rules={[{ required: true, message: '请填写查询到的登记状态' }]}><Input placeholder="如：存续" /></Form.Item>
          <Form.Item label="企业公示查询证据" required>
            <Form.Item name="evidence_asset_id" noStyle rules={[{ required: true, message: '请上传企业公示查询截图或 PDF' }]}><Input type="hidden" /></Form.Item>
            <Space><FileUpload accept="image/*,application/pdf" disabled={submitting} onUploaded={(asset) => { form.setFieldValue('evidence_asset_id', asset.id); setEvidenceUploaded(true) }} />{evidenceUploaded && <Tag color="green">已上传</Tag>}</Space>
          </Form.Item>
          <div className="grid grid-cols-1 gap-1 mb-4">
            {[
              ['entity_name_matches', '企业名称一致'],
              ['credit_code_matches', '统一社会信用代码一致'],
              ['legal_representative_matches', '法定代表人一致'],
              ['registration_status_valid', '登记状态正常'],
              ['registered_address_matches', '注册地址一致'],
              ['business_scope_matches', '经营范围与平台业务相符'],
            ].map(([field, label]) => <Form.Item key={field} name={field} valuePropName="checked" noStyle><Checkbox>{label}</Checkbox></Form.Item>)}
          </div>
          <Form.Item name="note" label="核验备注" rules={[{ max: 1000 }]}><Input.TextArea rows={2} /></Form.Item>
          {!reviewApproved && <Form.Item name="reject_reason" label="驳回原因" rules={[{ required: true, message: '请填写驳回原因' }, { max: 200 }]}><Input.TextArea rows={3} /></Form.Item>}
        </Form>
      </Modal>

      <Modal
        title="提交平台签署文件"
        open={platformSignTarget != null}
        onCancel={() => { setPlatformSignTarget(null); setPlatformFileUploaded(false); platformForm.resetFields() }}
        onOk={() => void submitPlatformSignature()}
        confirmLoading={submitting}
        okText="确认平台签署"
        cancelText="取消"
      >
        <Form form={platformForm} layout="vertical" className="mt-4">
          <Descriptions bordered column={1} size="small" className="mb-4">
            <Descriptions.Item label="协议编号">{platformSignTarget?.current_agreement?.agreement_number || '-'}</Descriptions.Item>
            <Descriptions.Item label="协议版本">{platformSignTarget?.current_agreement?.document_version || '-'}</Descriptions.Item>
          </Descriptions>
          <Form.Item label="双方签署的完整协议" required>
            <Form.Item name="platform_signed_asset_id" noStyle rules={[{ required: true, message: '请上传平台签署后的完整协议' }]}><Input type="hidden" /></Form.Item>
            <Space><FileUpload accept="image/*,application/pdf" disabled={submitting} onUploaded={(asset) => { platformForm.setFieldValue('platform_signed_asset_id', asset.id); setPlatformFileUploaded(true) }} />{platformFileUploaded && <Tag color="green">已上传</Tag>}</Space>
          </Form.Item>
          <Form.Item name="agreement_matches" valuePropName="checked" rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error('请确认协议一致性')) }]}>
            <Checkbox>已核对协议编号、版本、双方主体、正文和商家签署文件，平台已完成签署</Checkbox>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={documentPreview?.title}
        open={documentPreview != null}
        footer={<Button type="primary" onClick={downloadDocumentPreview}>下载原文件</Button>}
        onCancel={closeDocumentPreview}
        width={720}
      >
        {documentPreview?.contentType === 'application/pdf'
          ? <iframe src={documentPreview.url} title={documentPreview.title} style={{ width: '100%', height: '70vh', border: 0 }} />
          : documentPreview && <Image src={documentPreview.url} alt={documentPreview.title} style={{ width: '100%' }} />}
      </Modal>
    </div>
  )
}
