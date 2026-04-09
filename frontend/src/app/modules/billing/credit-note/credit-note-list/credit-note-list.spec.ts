import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { BillingService } from '../../../../services/billing';
import { CreditNoteList } from './credit-note-list';

describe('CreditNoteList', () => {
  let component: CreditNoteList;
  let fixture: ComponentFixture<CreditNoteList>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CreditNoteList],
      providers: [
        {
          provide: BillingService,
          useValue: {
            listCreditNotes: () => of([]),
            updateCreditNote: () => of({})
          }
        }
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreditNoteList);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
