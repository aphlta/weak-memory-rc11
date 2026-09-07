(* S6b：布尔性质 Prop 与静态 IND / promote
   对应 THEORY-v1 引理 5–6；具体 race/assert 检测器仍为参数（信任边界同附录）。 *)

From Coq Require Import Arith List.
Import ListNotations.
From Formal Require Import MiniGraph Reduction.

(** ---- 引理 5：布尔性质（存在性口径，不计见证条数） ---- *)

(** 坏执行标记：断言失败或数据竞争（相对一次完整 rf）。 *)
Definition BadMark := Rf -> list Read -> Prop.

(** 全量布尔性质：是否存在一致且 Bad 的执行。 *)
Definition Prop_full (C : Consistent) (Bad : BadMark) (rs : list Read) : Prop :=
  exists rf, C rf rs /\ Bad rf rs.

(** 约简侧布尔性质：是否存在「相关代表 + 存在性扩展」得到的 Bad 一致执行。
    与 Python 在约简路径上 evaluate 得到的布尔结论同构（不计条数）。 *)
Definition Prop_reduced (C : Consistent) (R : Relevant) (Bad : BadMark)
                        (rs : list Read) : Prop :=
  exists rf_rel rf,
    C rf rs /\
    (forall r, In r rs -> R r -> rf r = rf_rel r) /\
    Bad rf rs.

(** 引理 5：存在性口径下 Prop_full ↔ Prop_reduced（对任意 R）。
    左→右：取 rf_rel := rf；右→左：投影具体 rf。
    故见证条数不必相等，布尔结论一致。 *)
Theorem lemma5_prop_equiv :
  forall (C : Consistent) (R : Relevant) (Bad : BadMark) (rs : list Read),
    Prop_full C Bad rs <-> Prop_reduced C R Bad rs.
Proof.
  intros C R Bad rs.
  split.
  - intros [rf [HC HBad]].
    exists rf, rf.
    split; [exact HC|].
    split; [intros; reflexivity|exact HBad].
  - intros [rf_rel [rf [HC [_ HBad]]]].
    exists rf. split; [exact HC|exact HBad].
Qed.

(** 常用包装：race 与 assert 各自适用引理 5。 *)
Theorem lemma5_race_and_assert_equiv :
  forall C R Race AssertF rs,
    (Prop_full C Race rs <-> Prop_reduced C R Race rs) /\
    (Prop_full C AssertF rs <-> Prop_reduced C R AssertF rs).
Proof.
  intros. split; apply lemma5_prop_equiv.
Qed.

(** ---- 引理 6：静态 IND 与 promote 闭包 ---- *)

(** CritLoc(R)：相关读触及的地址。 *)
Definition CritLoc (R : Relevant) (rs : list Read) (l : Loc) : Prop :=
  exists r, In r rs /\ R r /\ rloc r = l.

(** 违例 1：同址伪噪声 —— 非相关读却读 CritLoc。 *)
Definition viol_shared_loc (R : Relevant) (rs : list Read) (r : Read) : Prop :=
  In r rs /\ ~ R r /\ CritLoc R rs (rloc r).

(** 违例 2：acquire 之后读 release-prefix 地址（抽象谓词，对应实现静态检查）。 *)
Definition AfterAcquire := Read -> Prop.
Definition InReleasePrefix := Loc -> Prop.

Definition viol_entangled (R : Relevant) (rs : list Read)
    (after_acq : AfterAcquire) (in_rp : InReleasePrefix) (r : Read) : Prop :=
  In r rs /\ ~ R r /\ after_acq r /\ in_rp (rloc r).

Definition Viol (R : Relevant) (rs : list Read)
    (after_acq : AfterAcquire) (in_rp : InReleasePrefix) (r : Read) : Prop :=
  viol_shared_loc R rs r \/ viol_entangled R rs after_acq in_rp r.

(** IND(R)：相对当前相关集无静态违例。 *)
Definition IND (R : Relevant) (rs : list Read)
    (after_acq : AfterAcquire) (in_rp : InReleasePrefix) : Prop :=
  forall r, ~ Viol R rs after_acq in_rp r.

(** 单步 promote：把相对 R0 的违例读并入相关集。 *)
Definition promote1 (R0 : Relevant) (rs : list Read)
    (after_acq : AfterAcquire) (in_rp : InReleasePrefix) : Relevant :=
  fun r => R0 r \/ Viol R0 rs after_acq in_rp r.

(** 闭包：相关集对「以自身为基准的 Viol」封闭（迭代 promote 的不动点性质）。 *)
Definition closed_under_viol (R : Relevant) (rs : list Read)
    (after_acq : AfterAcquire) (in_rp : InReleasePrefix) : Prop :=
  forall r, Viol R rs after_acq in_rp r -> R r.

(** 引理 6a：对 Viol 封闭 ⇒ IND。 *)
Theorem lemma6_closed_implies_ind :
  forall (R : Relevant) (rs : list Read)
         (after_acq : AfterAcquire) (in_rp : InReleasePrefix),
    closed_under_viol R rs after_acq in_rp ->
    IND R rs after_acq in_rp.
Proof.
  intros R rs after_acq in_rp Hclosed r Hviol.
  specialize (Hclosed r Hviol).
  destruct Hviol as [Hs | He].
  - destruct Hs as [_ [HnR _]]. contradiction.
  - destruct He as [_ [HnR _]]. contradiction.
Qed.

(** 引理 6b：若 IND(R0)，则噪声读（非 R0）不会因「同址/纠缠」静态规则被迫相关；
    此时取 R:=R0 与引理 1–5 的覆盖前提相容（覆盖由 R0⊇R_outcome 另行假设）。 *)
Theorem lemma6_ind_allows_noise_exclusion :
  forall (R0 : Relevant) (rs : list Read)
         (after_acq : AfterAcquire) (in_rp : InReleasePrefix) (r : Read),
    IND R0 rs after_acq in_rp ->
    In r rs ->
    ~ R0 r ->
    ~ CritLoc R0 rs (rloc r) /\
    ~ (after_acq r /\ in_rp (rloc r)).
Proof.
  intros R0 rs after_acq in_rp r Hind Hin HnR.
  split.
  - intros Hc. apply (Hind r). left. exact (conj Hin (conj HnR Hc)).
  - intros [Ha Hp]. apply (Hind r). right.
    exact (conj Hin (conj HnR (conj Ha Hp))).
Qed.

(** 引理 6c（promote 一步）：违例读被提升后属于新相关集。 *)
Theorem lemma6_promote1_absorbs_violators :
  forall (R0 : Relevant) (rs : list Read)
         (after_acq : AfterAcquire) (in_rp : InReleasePrefix) (r : Read),
    Viol R0 rs after_acq in_rp r ->
    promote1 R0 rs after_acq in_rp r.
Proof.
  intros R0 rs after_acq in_rp r H.
  unfold promote1. right. exact H.
Qed.

(** refuse：有违例则不用 R0 约简，回退「全体读相关」——此时 IND 平凡成立。 *)
Definition relevant_all (rs : list Read) : Relevant :=
  fun r => In r rs.

Theorem lemma6_refuse_all_is_ind :
  forall (rs : list Read) (after_acq : AfterAcquire) (in_rp : InReleasePrefix),
    IND (relevant_all rs) rs after_acq in_rp.
Proof.
  intros rs after_acq in_rp r Hviol.
  destruct Hviol as [Hs | He].
  - destruct Hs as [Hin [HnR _]].
    unfold relevant_all in HnR. contradiction.
  - destruct He as [Hin [HnR _]].
    unfold relevant_all in HnR. contradiction.
Qed.

(** 引理 6d：若 R 对 Viol 封闭，则 Prop 约简口径可用该 R（与引理 5 组合）。 *)
Theorem lemma6_closed_prop_equiv :
  forall (C : Consistent) (R : Relevant) (Bad : BadMark) (rs : list Read)
         (after_acq : AfterAcquire) (in_rp : InReleasePrefix),
    closed_under_viol R rs after_acq in_rp ->
    Prop_full C Bad rs <-> Prop_reduced C R Bad rs.
Proof.
  intros. apply lemma5_prop_equiv.
Qed.
