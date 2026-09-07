(* S6a：约简语义骨架与结局保持工作定理
   Consistent 为参数，不展开 mo/SC。 *)

From Coq Require Import List.
Import ListNotations.
From Formal Require Import MiniGraph.

(** 一致执行：rf + 读列表满足抽象一致性谓词。 *)
Definition Consistent := Rf -> list Read -> Prop.

Definition Exec (C : Consistent) (rs : list Read) : Rf -> Prop :=
  fun rf => C rf rs.

(** 观察结局相等（Out 成员相等的工作定义）。 *)
Definition outcomes_eq (Obs : ObsSet) (rs : list Read) (rf1 rf2 : Rf) : Prop :=
  forall x, Obs x -> observe rf1 rs x = observe rf2 rs x.

Definition Relevant := Read -> Prop.

(** 存在性扩展：对应 Python extend_mode=exists。 *)
Definition extends (C : Consistent) (R : Relevant) (rs : list Read)
                   (rf_rel : Rf) : Prop :=
  exists rf, C rf rs /\
    (forall r, In r rs -> R r -> rf r = rf_rel r).

Definition ExecR (C : Consistent) (R : Relevant) (rs : list Read) : Rf -> Prop :=
  fun rf_rel => extends C R rs rf_rel.

(** 假设 A1：相关集覆盖 outcome 读。 *)
Definition A1_covers_obs (Obs : ObsSet) (R : Relevant) (rs : list Read) : Prop :=
  forall r, In r rs -> Obs (target r) -> R r.

Definition A3_restrict_ok (C : Consistent) (R : Relevant) (rs : list Read) : Prop :=
  forall rf, C rf rs -> ExecR C R rs rf.

Lemma A3_holds_trivially :
  forall C R rs, A3_restrict_ok C R rs.
Proof.
  intros C R rs rf Hrf.
  unfold ExecR, extends.
  exists rf. split; [exact Hrf | intros; reflexivity].
Qed.

(** 健全（结局）：扩展得到的具体 rf 与约简代表在 Obs 上观察相同。 *)
Lemma sound_outcome_step :
  forall (Obs : ObsSet) (C : Consistent) (R : Relevant) (rs : list Read) rf_rel rf,
    A1_covers_obs Obs R rs ->
    C rf rs ->
    (forall r, In r rs -> R r -> rf r = rf_rel r) ->
    outcomes_eq Obs rs rf_rel rf.
Proof.
  intros Obs C R rs rf_rel rf HA1 HC Hagree x Hx.
  pose proof (lemma1_obs_depends_on_relevant_rf Obs rs rf_rel rf) as L.
  apply L; [| exact Hx ].
  unfold rf_agree_on_obs, relevant_obs.
  intros r Hin Hrel.
  assert (HR : R r) by (apply HA1; [exact Hin | exact Hrel]).
  specialize (Hagree r Hin HR).
  symmetry; exact Hagree.
Qed.

Lemma complete_outcome_step :
  forall (Obs : ObsSet) (C : Consistent) (R : Relevant) (rs : list Read) rf,
    C rf rs ->
    ExecR C R rs rf /\ outcomes_eq Obs rs rf rf.
Proof.
  intros Obs C R rs rf HC.
  split.
  - apply A3_holds_trivially; exact HC.
  - intros x Hx; reflexivity.
Qed.

(** T2⁺ 结局部分的工作形式（点式）。 *)
Theorem T2_plus_outcome_workhorse :
  forall (Obs : ObsSet) (C : Consistent) (R : Relevant) (rs : list Read) rf_rel rf,
    A1_covers_obs Obs R rs ->
    C rf rs ->
    (forall r, In r rs -> R r -> rf r = rf_rel r) ->
    outcomes_eq Obs rs rf_rel rf.
Proof.
  intros. eapply sound_outcome_step; eassumption.
Qed.
