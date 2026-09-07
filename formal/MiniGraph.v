(* S6a 迷你执行图编码：事件、rf 赋值、观察投影
   对应论文 THEORY-v1 引理 1 的离散有限情形。
   刻意不含完整 sw/mo/SC；一致性谓词在 Reduction.v 中参数化。 *)

From Coq Require Import Arith Bool List.
Import ListNotations.

(** 地址 / 值 / 事件标识：有限离散域用 nat 表示。 *)
Definition Loc := nat.
Definition Val := nat.
Definition EvId := nat.

(** 写事件：固定地址与写入值（含虚拟初值写）。 *)
Record Write := {
  wid : EvId;
  wloc : Loc;
  wval : Val
}.

(** 读事件：读地址 + 观察目标变量（教具中 target）。 *)
Record Read := {
  rid : EvId;
  rloc : Loc;
  target : Loc
}.

(** rf 赋值：每个读映射到一个写。 *)
Definition Rf := Read -> Write.

(** 观察变量集合。 *)
Definition ObsSet := Loc -> Prop.

(** 基础相关读（outcome 维）：目标落在 Obs 中。 *)
Definition relevant_obs (Obs : ObsSet) (r : Read) : Prop :=
  Obs (target r).

(** 从读列表中找第一个 target = x 的读。 *)
Fixpoint find_read_for (x : Loc) (rs : list Read) : option Read :=
  match rs with
  | [] => None
  | r :: rs' =>
      if Nat.eqb (target r) x then Some r else find_read_for x rs'
  end.

(** 观察投影。 *)
Definition observe (rf : Rf) (rs : list Read) (x : Loc) : option Val :=
  match find_read_for x rs with
  | Some r => Some (wval (rf r))
  | None => None
  end.

(** 两 rf 在 Obs 相关读上一致。 *)
Definition rf_agree_on_obs (Obs : ObsSet) (rf1 rf2 : Rf) (rs : list Read) : Prop :=
  forall r, In r rs -> relevant_obs Obs r -> rf1 r = rf2 r.

Lemma find_read_for_sound :
  forall x rs r,
    find_read_for x rs = Some r ->
    In r rs /\ target r = x.
Proof.
  intros x rs r H.
  induction rs as [|r' rs' IH]; simpl in *.
  - discriminate.
  - destruct (Nat.eqb (target r') x) eqn:E.
    + inversion H; subst; split; [left; reflexivity|].
      apply Nat.eqb_eq in E; exact E.
    + apply IH in H. destruct H as [Hin Heq].
      split; [right; exact Hin | exact Heq].
Qed.

(** 引理 1（离散版 / outcome 维）：观察投影由 Obs 相关读上的 rf 决定。 *)
Theorem lemma1_obs_depends_on_relevant_rf :
  forall (Obs : ObsSet) (rs : list Read) (rf1 rf2 : Rf),
    rf_agree_on_obs Obs rf1 rf2 rs ->
    forall x, Obs x -> observe rf1 rs x = observe rf2 rs x.
Proof.
  intros Obs rs rf1 rf2 Hagree x Hx.
  unfold observe.
  destruct (find_read_for x rs) as [r|] eqn:Hf; [|reflexivity].
  apply find_read_for_sound in Hf.
  destruct Hf as [Hin Htgt].
  assert (Hrel : relevant_obs Obs r).
  { unfold relevant_obs. rewrite Htgt. exact Hx. }
  specialize (Hagree r Hin Hrel).
  rewrite Hagree.
  reflexivity.
Qed.

Corollary obs_determined_by_rf_on_obs_reads :
  forall (Obs : ObsSet) (rs : list Read) (rf1 rf2 : Rf),
    (forall r, In r rs -> Obs (target r) -> rf1 r = rf2 r) ->
    forall x, Obs x -> observe rf1 rs x = observe rf2 rs x.
Proof.
  intros Obs rs rf1 rf2 H.
  apply lemma1_obs_depends_on_relevant_rf.
  unfold rf_agree_on_obs, relevant_obs.
  exact H.
Qed.
